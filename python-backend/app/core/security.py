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
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
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
    return create_jwt_token(subject, ACCESS_TOKEN_TYPE, expire_seconds)


def create_refresh_token(subject: str, expires_in: int | None = None) -> str:
    expire_seconds = expires_in or settings.auth_refresh_token_expire_seconds
    return create_jwt_token(subject, REFRESH_TOKEN_TYPE, expire_seconds)


def create_jwt_token(subject: str, token_type: str, expires_in: int) -> str:
    issued_at = int(time.time())
    header = {"typ": "JWT", "alg": TOKEN_ALGORITHM}
    payload = {
        "iss": settings.auth_token_issuer,
        "aud": settings.auth_token_audience,
        "sub": subject,
        "iat": issued_at,
        "nbf": issued_at,
        "exp": issued_at + expires_in,
        "jti": secrets.token_urlsafe(24),
        "type": token_type,
    }
    header_part = _json_part(header)
    payload_part = _json_part(payload)
    signing_input = f"{header_part}.{payload_part}"
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    return decode_jwt_token(token, expected_type=ACCESS_TOKEN_TYPE)


def decode_refresh_token(token: str) -> dict[str, Any] | None:
    return decode_jwt_token(token, expected_type=REFRESH_TOKEN_TYPE)


def decode_jwt_token(token: str, expected_type: str | None = None) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None

    header_part, payload_part, signature = parts
    signing_input = f"{header_part}.{payload_part}"
    if not hmac.compare_digest(_sign(signing_input), signature):
        return None

    try:
        header = json.loads(_base64_url_decode(header_part))
        payload = json.loads(_base64_url_decode(payload_part))
    except (binascii.Error, json.JSONDecodeError, TypeError, ValueError):
        return None

    now = int(time.time())
    if header.get("alg") != TOKEN_ALGORITHM or header.get("typ") != "JWT":
        return None
    if payload.get("iss") != settings.auth_token_issuer:
        return None
    if payload.get("aud") != settings.auth_token_audience:
        return None
    if expected_type and payload.get("type") != expected_type:
        return None
    if int(payload.get("nbf", 0)) > now:
        return None
    if int(payload.get("exp", 0)) < now:
        return None
    if not payload.get("jti") or not payload.get("sub"):
        return None
    return payload


def _sign(signing_input: str) -> str:
    digest = hmac.new(
        settings.auth_secret_key.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _base64_url_encode(digest)


def _json_part(payload: dict[str, Any]) -> str:
    return _base64_url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


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
