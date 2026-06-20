from time import time
from typing import Protocol

import redis.asyncio as redis


class IdempotencyStore(Protocol):
    async def acquire(self, key: str, ttl_seconds: int) -> bool: ...

    async def release(self, key: str) -> None: ...


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._expires_at: dict[str, float] = {}

    async def acquire(self, key: str, ttl_seconds: int) -> bool:
        self._purge_expired()
        if key in self._expires_at:
            return False
        self._expires_at[key] = time() + ttl_seconds
        return True

    async def release(self, key: str) -> None:
        self._expires_at.pop(key, None)

    def _purge_expired(self) -> None:
        now = time()
        for key, expires_at in list(self._expires_at.items()):
            if expires_at <= now:
                self._expires_at.pop(key, None)


class RedisIdempotencyStore:
    def __init__(self, redis_url: str, key_prefix: str = "ragent:idempotency") -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix

    async def acquire(self, key: str, ttl_seconds: int) -> bool:
        result = await self._client.set(self._key(key), "1", nx=True, ex=ttl_seconds)
        return bool(result)

    async def release(self, key: str) -> None:
        await self._client.delete(self._key(key))

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"
