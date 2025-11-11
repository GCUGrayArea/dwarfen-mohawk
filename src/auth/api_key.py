"""API key validation and hashing utilities."""

import bcrypt


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using bcrypt.

    Args:
        api_key: Plain text API key to hash

    Returns:
        Bcrypt hash of the API key
    """
    salt = bcrypt.gensalt()
    key_bytes = api_key.encode("utf-8")
    hashed = bcrypt.hashpw(key_bytes, salt)
    return hashed.decode("utf-8")


def verify_api_key(api_key: str, key_hash: str) -> bool:
    """
    Verify an API key against its hash.

    Args:
        api_key: Plain text API key to verify
        key_hash: Bcrypt hash to verify against

    Returns:
        True if the API key matches the hash, False otherwise
    """
    key_bytes = api_key.encode("utf-8")
    hash_bytes = key_hash.encode("utf-8")
    return bcrypt.checkpw(key_bytes, hash_bytes)
