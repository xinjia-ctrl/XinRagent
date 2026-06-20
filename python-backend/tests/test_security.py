import hashlib

from app.core.security import hash_password, needs_password_rehash, verify_password


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
