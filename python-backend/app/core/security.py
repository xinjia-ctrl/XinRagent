import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.core.config import settings

TOKEN_ALGORITHM = "HS256"
PASSWORD_ALGORITHM = "pbkdf2_sha256"
LEGACY_SHA256_ALGORITHM = "sha256"
PASSWORD_SALT_BYTES = 16
PASSWORD_DIGEST_BYTES = 32


def hash_password(password: str) -> str:
    iterations = _password_iterations()
    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
    digest = _pbkdf2_digest(password, salt, iterations)
    return (
        f"{PASSWORD_ALGORITHM}${iterations}$"
        f"{_base64_url_encode(salt)}${_base64_url_encode(digest)}"
    )


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    if password_hash.startswith(f"{PASSWORD_ALGORITHM}$"):
        return _verify_pbkdf2_password(plain_password, password_hash)
    if password_hash.startswith(f"{LEGACY_SHA256_ALGORITHM}$"):
        return _verify_legacy_sha256_password(plain_password, password_hash)
    return False


def needs_password_rehash(password_hash: str) -> bool:
    if not password_hash.startswith(f"{PASSWORD_ALGORITHM}$"):
        return True
    parts = password_hash.split("$")
    if len(parts) != 4:
        return True
    try:
        iterations = int(parts[1])
    except ValueError:
        return True
    return iterations < _password_iterations()


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


def _verify_pbkdf2_password(plain_password: str, password_hash: str) -> bool:
    parts = password_hash.split("$")
    if len(parts) != 4:
        return False
    _, iterations_text, salt_part, digest_part = parts
    try:
        iterations = int(iterations_text)
        if iterations < 100000 or iterations > 2000000:
            return False
        salt = _base64_url_decode(salt_part)
    except (binascii.Error, ValueError, TypeError):
        return False
    expected_digest = _pbkdf2_digest(plain_password, salt, iterations)
    return hmac.compare_digest(_base64_url_encode(expected_digest), digest_part)


def _verify_legacy_sha256_password(plain_password: str, password_hash: str) -> bool:
    digest = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(f"{LEGACY_SHA256_ALGORITHM}${digest}", password_hash)


def _pbkdf2_digest(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=PASSWORD_DIGEST_BYTES,
    )


def _password_iterations() -> int:
    return min(max(settings.auth_password_pbkdf2_iterations, 100000), 2000000)


def _base64_url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64_url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
