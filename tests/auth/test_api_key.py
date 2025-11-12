"""Unit tests for API key validation and hashing."""


from src.auth.api_key import hash_api_key, verify_api_key


def test_hash_api_key() -> None:
    """Test that API key hashing produces a valid bcrypt hash."""
    api_key = "test_key_12345"
    hashed = hash_api_key(api_key)

    # Bcrypt hashes start with $2b$ and are 60 characters
    assert hashed.startswith("$2b$")
    assert len(hashed) == 60


def test_hash_api_key_different_each_time() -> None:
    """Test that hashing the same key produces different hashes (salt)."""
    api_key = "test_key_12345"
    hash1 = hash_api_key(api_key)
    hash2 = hash_api_key(api_key)

    # Due to random salt, hashes should be different
    assert hash1 != hash2


def test_verify_api_key_valid() -> None:
    """Test that verify_api_key returns True for valid key."""
    api_key = "test_key_12345"
    hashed = hash_api_key(api_key)

    assert verify_api_key(api_key, hashed) is True


def test_verify_api_key_invalid() -> None:
    """Test that verify_api_key returns False for invalid key."""
    api_key = "test_key_12345"
    wrong_key = "wrong_key_67890"
    hashed = hash_api_key(api_key)

    assert verify_api_key(wrong_key, hashed) is False


def test_verify_api_key_empty_string() -> None:
    """Test verify_api_key with empty string."""
    api_key = ""
    hashed = hash_api_key(api_key)

    assert verify_api_key(api_key, hashed) is True
    assert verify_api_key("not_empty", hashed) is False
