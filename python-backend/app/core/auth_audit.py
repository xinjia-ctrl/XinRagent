import json
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from time import time
from typing import Protocol

import redis.asyncio as redis

from app.core.config import settings


@dataclass(frozen=True)
class AuthAuditEvent:
    event_type: str
    success: bool
    username: str | None = None
    user_id: str | None = None
    reason: str | None = None
    token_jti: str | None = None
    created_at: float = field(default_factory=time)


class AuthAuditStore(Protocol):
    async def record(self, event: AuthAuditEvent) -> None: ...


class InMemoryAuthAuditStore:
    def __init__(self) -> None:
        self.events: list[AuthAuditEvent] = []

    async def record(self, event: AuthAuditEvent) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()


class RedisAuthAuditStore:
    def __init__(self, redis_url: str, key_prefix: str, max_events: int = 10000) -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._key = f"{key_prefix}:events"
        self._max_events = max_events

    async def record(self, event: AuthAuditEvent) -> None:
        await self._client.lpush(self._key, json.dumps(asdict(event), ensure_ascii=False))
        await self._client.ltrim(self._key, 0, self._max_events - 1)


@lru_cache
def get_auth_audit_store() -> AuthAuditStore:
    if settings.auth_audit_backend.lower() == "redis":
        return RedisAuthAuditStore(settings.redis_url, settings.auth_audit_key_prefix)
    return InMemoryAuthAuditStore()


async def record_auth_audit(
    event_type: str,
    *,
    success: bool,
    username: str | None = None,
    user_id: str | None = None,
    reason: str | None = None,
    token_jti: str | None = None,
) -> None:
    await get_auth_audit_store().record(
        AuthAuditEvent(
            event_type=event_type,
            success=success,
            username=username,
            user_id=user_id,
            reason=reason,
            token_jti=token_jti,
        ),
    )
