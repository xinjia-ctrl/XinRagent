from functools import lru_cache
from time import time
from typing import Protocol

import redis.asyncio as redis

from app.core.config import settings


class TokenRevocationStore(Protocol):
    async def revoke(self, jti: str, expires_at: int) -> None: ...

    async def is_revoked(self, jti: str) -> bool: ...


class InMemoryTokenRevocationStore:
    def __init__(self) -> None:
        self._revoked: dict[str, int] = {}

    async def revoke(self, jti: str, expires_at: int) -> None:
        self._purge_expired()
        self._revoked[jti] = expires_at

    async def is_revoked(self, jti: str) -> bool:
        self._purge_expired()
        return jti in self._revoked

    def clear(self) -> None:
        self._revoked.clear()

    def _purge_expired(self) -> None:
        now = int(time())
        for jti, expires_at in list(self._revoked.items()):
            if expires_at <= now:
                self._revoked.pop(jti, None)


class RedisTokenRevocationStore:
    def __init__(self, redis_url: str, key_prefix: str = "ragent:auth:revoked") -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix

    async def revoke(self, jti: str, expires_at: int) -> None:
        ttl_seconds = max(expires_at - int(time()), 1)
        await self._client.set(self._key(jti), "1", ex=ttl_seconds)

    async def is_revoked(self, jti: str) -> bool:
        return bool(await self._client.exists(self._key(jti)))

    def _key(self, jti: str) -> str:
        return f"{self._key_prefix}:{jti}"


@lru_cache
def get_token_revocation_store() -> TokenRevocationStore:
    if settings.auth_token_store_backend.lower() == "redis":
        return RedisTokenRevocationStore(settings.redis_url)
    return InMemoryTokenRevocationStore()
