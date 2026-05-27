import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.core.config import settings

TOKEN_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return f"sha256${digest}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    if password_hash.startswith("sha256$"):
        return hmac.compare_digest(hash_password(plain_password), password_hash)
    return hmac.compare_digest(plain_password, password_hash)


def create_access_token(subject: str, expires_in: int | None = None) -> str:
    expire_seconds = expires_in or settings.auth_token_expire_seconds
    payload = {
        "sub": subject,
        "exp": int(time.time()) + expire_seconds,
        "alg": TOKEN_ALGORITHM,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_part = _base64_url_encode(payload_bytes)
    signature = _sign(payload_part)
    return f"{payload_part}.{signature}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 2:
        return None

    payload_part, signature = parts
    if not hmac.compare_digest(_sign(payload_part), signature):
        return None

    try:
        payload = json.loads(_base64_url_decode(payload_part))
    except (json.JSONDecodeError, ValueError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def _sign(payload_part: str) -> str:
    digest = hmac.new(
        settings.auth_secret_key.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _base64_url_encode(digest)


def _base64_url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64_url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
