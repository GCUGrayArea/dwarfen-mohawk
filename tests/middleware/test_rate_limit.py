"""Unit tests for rate limiting middleware."""

import time

import pytest

from src.exceptions import RateLimitError
from src.middleware.rate_limit import RateLimiter


@pytest.fixture
def rate_limiter() -> RateLimiter:
    """Create a fresh RateLimiter instance for each test."""
    limiter = RateLimiter()
    limiter.clear_all()
    return limiter


def test_rate_limit_allows_under_limit(rate_limiter: RateLimiter) -> None:
    """Test that requests under limit are allowed."""
    key_id = "test_key_1"
    limit = 10

    # Should allow all 10 requests
    for _ in range(10):
        rate_limiter.check_rate_limit(key_id, limit)


def test_rate_limit_blocks_over_limit(rate_limiter: RateLimiter) -> None:
    """Test that requests over limit are blocked."""
    key_id = "test_key_2"
    limit = 5

    # First 5 should succeed
    for _ in range(5):
        rate_limiter.check_rate_limit(key_id, limit)

    # 6th should raise RateLimitError
    with pytest.raises(RateLimitError) as exc_info:
        rate_limiter.check_rate_limit(key_id, limit)

    error = exc_info.value
    assert error.status_code == 429
    assert error.error_code == "RATE_LIMIT_EXCEEDED"
    assert error.retry_after > 0


def test_rate_limit_resets_after_window(rate_limiter: RateLimiter) -> None:
    """Test that rate limit resets after time window passes."""
    key_id = "test_key_3"
    limit = 2

    # Use up limit
    for _ in range(2):
        rate_limiter.check_rate_limit(key_id, limit)

    # Should be blocked
    with pytest.raises(RateLimitError):
        rate_limiter.check_rate_limit(key_id, limit)

    # Mock time passing by directly manipulating internal state
    # In production, would wait 60 seconds
    rate_limiter._requests[key_id] = (0, time.time() - 61)

    # Should now be allowed
    rate_limiter.check_rate_limit(key_id, limit)


def test_rate_limit_separate_keys(rate_limiter: RateLimiter) -> None:
    """Test that different keys have independent rate limits."""
    key_id_1 = "test_key_4"
    key_id_2 = "test_key_5"
    limit = 3

    # Use up limit for key_id_1
    for _ in range(3):
        rate_limiter.check_rate_limit(key_id_1, limit)

    # key_id_1 should be blocked
    with pytest.raises(RateLimitError):
        rate_limiter.check_rate_limit(key_id_1, limit)

    # key_id_2 should still be allowed
    for _ in range(3):
        rate_limiter.check_rate_limit(key_id_2, limit)


def test_rate_limit_reset_key(rate_limiter: RateLimiter) -> None:
    """Test that reset_key clears counter for a specific key."""
    key_id = "test_key_6"
    limit = 2

    # Use up limit
    for _ in range(2):
        rate_limiter.check_rate_limit(key_id, limit)

    # Reset the key
    rate_limiter.reset_key(key_id)

    # Should be allowed again
    for _ in range(2):
        rate_limiter.check_rate_limit(key_id, limit)


def test_rate_limit_clear_all(rate_limiter: RateLimiter) -> None:
    """Test that clear_all resets all counters."""
    limit = 1

    # Use up limits for multiple keys
    rate_limiter.check_rate_limit("key_1", limit)
    rate_limiter.check_rate_limit("key_2", limit)

    # Both should be blocked
    with pytest.raises(RateLimitError):
        rate_limiter.check_rate_limit("key_1", limit)
    with pytest.raises(RateLimitError):
        rate_limiter.check_rate_limit("key_2", limit)

    # Clear all
    rate_limiter.clear_all()

    # Both should be allowed again
    rate_limiter.check_rate_limit("key_1", limit)
    rate_limiter.check_rate_limit("key_2", limit)


def test_rate_limit_error_details(rate_limiter: RateLimiter) -> None:
    """Test that RateLimitError includes correct details."""
    key_id = "test_key_7"
    limit = 1

    # Use up limit
    rate_limiter.check_rate_limit(key_id, limit)

    # Try to exceed
    with pytest.raises(RateLimitError) as exc_info:
        rate_limiter.check_rate_limit(key_id, limit)

    error = exc_info.value
    assert "limit" in error.details
    assert error.details["limit"] == limit
    assert "window_seconds" in error.details
    assert error.details["window_seconds"] == 60
    assert "retry_after" in error.details
