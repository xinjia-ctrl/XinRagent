from time import time
from typing import Protocol

import redis.asyncio as redis

from app.core.exceptions import RagentException


class UploadRateLimiter(Protocol):
    async def check(self, key: str) -> None: ...


class InMemoryUploadRateLimiter:
    def __init__(self, limit_per_minute: int, enabled: bool = True) -> None:
        self.limit_per_minute = limit_per_minute
        self.enabled = enabled
        self._windows: dict[str, tuple[int, int]] = {}

    async def check(self, key: str) -> None:
        if not self.enabled:
            return
        window = int(time() // 60)
        current_window, count = self._windows.get(key, (window, 0))
        if current_window != window:
            count = 0
            current_window = window
        count += 1
        self._windows[key] = (current_window, count)
        if count > self.limit_per_minute:
            raise RagentException(message="上传过于频繁，请稍后再试", code="UPLOAD_RATE_LIMITED", status_code=429)


class RedisUploadRateLimiter:
    def __init__(
        self,
        redis_url: str,
        key_prefix: str,
        limit_per_minute: int,
        enabled: bool = True,
    ) -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self.key_prefix = key_prefix
        self.limit_per_minute = limit_per_minute
        self.enabled = enabled

    async def check(self, key: str) -> None:
        if not self.enabled:
            return
        redis_key = f"{self.key_prefix}:{key}:{int(time() // 60)}"
        count = await self._client.incr(redis_key)
        if int(count) == 1:
            await self._client.expire(redis_key, 90)
        if int(count) > self.limit_per_minute:
            raise RagentException(message="上传过于频繁，请稍后再试", code="UPLOAD_RATE_LIMITED", status_code=429)
