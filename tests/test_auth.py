"""Authentication tests."""

from app.services.auth import KEY_PREFIX, generate_api_key, hash_api_key, verify_api_key


def test_key_format():
    key = generate_api_key()
    assert key.startswith(KEY_PREFIX)
    assert len(key) > 20


def test_hash_and_verify():
    key = generate_api_key()
    hashed = hash_api_key(key)
    assert hashed != key
    assert verify_api_key(key, hashed)
    assert not verify_api_key("wrong-key", hashed)


def test_different_keys_different_hashes():
    key1 = generate_api_key()
    key2 = generate_api_key()
    hash1 = hash_api_key(key1)
    hash2 = hash_api_key(key2)
    assert hash1 != hash2
