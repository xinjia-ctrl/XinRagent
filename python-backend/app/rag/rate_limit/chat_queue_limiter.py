import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol

import redis.asyncio as redis


StatusCallback = Callable[["QueueStatus"], Awaitable[None] | None]


@dataclass(slots=True)
class QueueStatus:
    request_id: str
    status: str
    position: int | None
    waiting_seconds: float
    timeout_seconds: float
    max_concurrency: int


class QueueWatcher(Protocol):
    async def __aenter__(self) -> "QueueWatcher": ...

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...

    async def wait(self, timeout: float) -> None: ...


class QueueBackend(Protocol):
    def watcher(self) -> QueueWatcher: ...

    async def enqueue(self, request_id: str, timeout_seconds: float) -> None: ...

    async def try_acquire(
        self,
        request_id: str,
        max_concurrency: int,
        active_ttl_seconds: int,
    ) -> bool: ...

    async def position(self, request_id: str) -> int | None: ...

    async def remove(self, request_id: str) -> None: ...

    async def release(self, request_id: str) -> None: ...


@dataclass(slots=True)
class QueuePermit:
    acquired: bool
    request_id: str
    reason: str | None = None
    _release_callback: Callable[[], Awaitable[None]] | None = None
    _released: bool = False

    async def release(self) -> None:
        if not self.acquired or self._released or self._release_callback is None:
            return
        self._released = True
        await self._release_callback()


class DisabledQueueWatcher:
    async def __aenter__(self) -> "DisabledQueueWatcher":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def wait(self, timeout: float) -> None:
        await asyncio.sleep(min(timeout, 0))


class InMemoryQueueWatcher:
    def __init__(self, condition: asyncio.Condition) -> None:
        self._condition = condition

    async def __aenter__(self) -> "InMemoryQueueWatcher":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def wait(self, timeout: float) -> None:
        if timeout <= 0:
            return
        async with self._condition:
            try:
                await asyncio.wait_for(self._condition.wait(), timeout=timeout)
            except TimeoutError:
                return


class InMemoryQueueBackend:
    """测试和单进程开发用后端，生产环境使用 RedisQueueBackend。"""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._queue: list[str] = []
        self._active = 0

    def watcher(self) -> QueueWatcher:
        return InMemoryQueueWatcher(self._condition)

    async def enqueue(self, request_id: str, timeout_seconds: float) -> None:
        async with self._condition:
            if request_id not in self._queue:
                self._queue.append(request_id)
            self._condition.notify_all()

    async def try_acquire(
        self,
        request_id: str,
        max_concurrency: int,
        active_ttl_seconds: int,
    ) -> bool:
        async with self._condition:
            if not self._queue or self._queue[0] != request_id or self._active >= max_concurrency:
                return False
            self._queue.pop(0)
            self._active += 1
            self._condition.notify_all()
            return True

    async def position(self, request_id: str) -> int | None:
        async with self._condition:
            try:
                return self._queue.index(request_id) + 1
            except ValueError:
                return None

    async def remove(self, request_id: str) -> None:
        async with self._condition:
            if request_id in self._queue:
                self._queue.remove(request_id)
            self._condition.notify_all()

    async def release(self, request_id: str) -> None:
        async with self._condition:
            self._active = max(0, self._active - 1)
            self._condition.notify_all()


class RedisQueueWatcher:
    def __init__(self, client: redis.Redis, channel_key: str) -> None:
        self._client = client
        self._channel_key = channel_key
        self._pubsub: Any | None = None

    async def __aenter__(self) -> "RedisQueueWatcher":
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(self._channel_key)
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._pubsub is None:
            return
        await self._pubsub.unsubscribe(self._channel_key)
        await self._pubsub.aclose()

    async def wait(self, timeout: float) -> None:
        if self._pubsub is None or timeout <= 0:
            return
        message = await self._pubsub.get_message(
            ignore_subscribe_messages=True,
            timeout=timeout,
        )
        if message is None:
            return


class RedisQueueBackend:
    ACQUIRE_SCRIPT = """
local rank = redis.call('ZRANK', KEYS[2], ARGV[1])
if not rank then
    return -1
end
if tonumber(rank) ~= 0 then
    return 0
end
local active = tonumber(redis.call('GET', KEYS[1]) or '0')
local max_active = tonumber(ARGV[2])
if active >= max_active then
    return 0
end
redis.call('ZREM', KEYS[2], ARGV[1])
redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return 1
"""

    RELEASE_SCRIPT = """
local active = tonumber(redis.call('GET', KEYS[1]) or '0')
if active <= 1 then
    redis.call('DEL', KEYS[1])
else
    redis.call('DECR', KEYS[1])
end
redis.call('PUBLISH', KEYS[2], ARGV[1])
return 1
"""

    def __init__(self, redis_url: str, key_prefix: str) -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._active_key = f"{key_prefix}:active"
        self._queue_key = f"{key_prefix}:queue"
        self._seq_key = f"{key_prefix}:seq"
        self._notify_key = f"{key_prefix}:notify"

    def watcher(self) -> QueueWatcher:
        return RedisQueueWatcher(self._client, self._notify_key)

    async def enqueue(self, request_id: str, timeout_seconds: float) -> None:
        score = await self._client.incr(self._seq_key)
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.zadd(self._queue_key, {request_id: score}, nx=True)
            pipe.expire(self._queue_key, int(timeout_seconds) + 60)
            pipe.expire(self._seq_key, int(timeout_seconds) + 60)
            pipe.publish(self._notify_key, request_id)
            await pipe.execute()

    async def try_acquire(
        self,
        request_id: str,
        max_concurrency: int,
        active_ttl_seconds: int,
    ) -> bool:
        result = await self._client.eval(
            self.ACQUIRE_SCRIPT,
            2,
            self._active_key,
            self._queue_key,
            request_id,
            max_concurrency,
            active_ttl_seconds,
        )
        return int(result) == 1

    async def position(self, request_id: str) -> int | None:
        rank = await self._client.zrank(self._queue_key, request_id)
        if rank is None:
            return None
        return int(rank) + 1

    async def remove(self, request_id: str) -> None:
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.zrem(self._queue_key, request_id)
            pipe.publish(self._notify_key, request_id)
            await pipe.execute()

    async def release(self, request_id: str) -> None:
        await self._client.eval(
            self.RELEASE_SCRIPT,
            2,
            self._active_key,
            self._notify_key,
            request_id,
        )


class ChatQueueLimiter:
    def __init__(
        self,
        *,
        enabled: bool,
        backend: QueueBackend | None = None,
        max_concurrency: int = 3,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.5,
        active_ttl_seconds: int = 120,
    ) -> None:
        self.enabled = enabled
        self.backend = backend
        self.max_concurrency = max_concurrency
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.active_ttl_seconds = active_ttl_seconds

    @classmethod
    def disabled(cls) -> "ChatQueueLimiter":
        return cls(enabled=False)

    async def acquire(
        self,
        request_id: str,
        on_status: StatusCallback | None = None,
    ) -> QueuePermit:
        if not self.enabled or self.backend is None:
            return QueuePermit(acquired=True, request_id=request_id)
        if self.max_concurrency < 1:
            return QueuePermit(acquired=False, request_id=request_id, reason="capacity_disabled")

        started_at = monotonic()
        deadline = started_at + self.timeout_seconds
        acquired = False
        await self.backend.enqueue(request_id, self.timeout_seconds)
        try:
            async with self.backend.watcher() as watcher:
                while True:
                    acquired = await self.backend.try_acquire(
                        request_id,
                        self.max_concurrency,
                        self.active_ttl_seconds,
                    )
                    if acquired:
                        await self._emit_status(on_status, request_id, "acquired", None, started_at)
                        return QueuePermit(
                            acquired=True,
                            request_id=request_id,
                            _release_callback=lambda: self.backend.release(request_id),
                        )

                    position = await self.backend.position(request_id)
                    await self._emit_status(on_status, request_id, "waiting", position, started_at)
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        await self.backend.remove(request_id)
                        await self._emit_status(on_status, request_id, "timeout", None, started_at)
                        return QueuePermit(acquired=False, request_id=request_id, reason="timeout")
                    await watcher.wait(min(self.poll_interval_seconds, remaining))
        except BaseException:
            if not acquired:
                await self.backend.remove(request_id)
            raise

    async def _emit_status(
        self,
        on_status: StatusCallback | None,
        request_id: str,
        status: str,
        position: int | None,
        started_at: float,
    ) -> None:
        if on_status is None:
            return
        result = on_status(
            QueueStatus(
                request_id=request_id,
                status=status,
                position=position,
                waiting_seconds=round(monotonic() - started_at, 3),
                timeout_seconds=self.timeout_seconds,
                max_concurrency=self.max_concurrency,
            ),
        )
        if inspect.isawaitable(result):
            await result
