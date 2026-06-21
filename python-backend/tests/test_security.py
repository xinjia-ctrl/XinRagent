import hashlib

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    needs_password_rehash,
    verify_password,
)


def test_hash_password_uses_salted_pbkdf2_hash() -> None:
    first_hash = hash_password("secret")
    second_hash = hash_password("secret")

    assert first_hash.startswith("pbkdf2_sha256$")
    assert second_hash.startswith("pbkdf2_sha256$")
    assert first_hash != second_hash
    assert verify_password("secret", first_hash)
    assert verify_password("wrong", first_hash) is False


def test_verify_password_rejects_plaintext_hash_compatibility() -> None:
    assert verify_password("secret", "secret") is False


def test_legacy_sha256_password_still_verifies_but_needs_rehash() -> None:
    legacy_hash = f"sha256${hashlib.sha256('secret'.encode('utf-8')).hexdigest()}"

    assert verify_password("secret", legacy_hash)
    assert needs_password_rehash(legacy_hash)


def test_access_and_refresh_tokens_are_standard_jwt_and_type_scoped() -> None:
    access_token = create_access_token("user-1", expires_in=60)
    refresh_token = create_refresh_token("user-1", expires_in=120)

    access_payload = decode_access_token(access_token)
    refresh_payload = decode_refresh_token(refresh_token)

    assert len(access_token.split(".")) == 3
    assert len(refresh_token.split(".")) == 3
    assert access_payload is not None
    assert refresh_payload is not None
    assert access_payload["sub"] == "user-1"
    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert decode_access_token(refresh_token) is None
    assert decode_refresh_token(access_token) is None
