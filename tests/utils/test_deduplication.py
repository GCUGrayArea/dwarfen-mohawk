"""Tests for deduplication cache."""

import time
from unittest.mock import patch

import pytest

from src.utils.deduplication import DeduplicationCache


def test_cache_initialization():
    """Test cache initializes with correct window."""
    cache = DeduplicationCache(window_seconds=300)
    assert cache.window_seconds == 300
    assert len(cache._cache) == 0


def test_fingerprint_generation():
    """Test fingerprint generation is consistent."""
    cache = DeduplicationCache()

    payload1 = {"user_id": "123", "action": "login"}
    payload2 = {"action": "login", "user_id": "123"}  # Different order

    fp1 = cache._generate_fingerprint("user.login", payload1)
    fp2 = cache._generate_fingerprint("user.login", payload2)

    # Same content, different order = same fingerprint
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA256 hex length


def test_fingerprint_differs_for_different_events():
    """Test different events produce different fingerprints."""
    cache = DeduplicationCache()

    fp1 = cache._generate_fingerprint(
        "user.login", {"user_id": "123"}
    )
    fp2 = cache._generate_fingerprint(
        "user.login", {"user_id": "456"}
    )
    fp3 = cache._generate_fingerprint(
        "user.logout", {"user_id": "123"}
    )

    assert fp1 != fp2  # Different payload
    assert fp1 != fp3  # Different event type
    assert fp2 != fp3


def test_check_and_add_new_event():
    """Test adding new event returns None."""
    cache = DeduplicationCache()

    result = cache.check_and_add(
        "user.signup", {"email": "test@example.com"}, "event-123"
    )

    assert result is None
    assert len(cache._cache) == 1


def test_check_and_add_duplicate_event():
    """Test duplicate event returns existing ID."""
    cache = DeduplicationCache()

    # First event
    result1 = cache.check_and_add(
        "user.signup", {"email": "test@example.com"}, "event-123"
    )
    assert result1 is None

    # Duplicate event
    result2 = cache.check_and_add(
        "user.signup", {"email": "test@example.com"}, "event-456"
    )
    assert result2 == "event-123"


def test_duplicate_with_different_order():
    """Test duplicate detection with different payload order."""
    cache = DeduplicationCache()

    payload1 = {"user_id": "123", "email": "test@example.com"}
    payload2 = {"email": "test@example.com", "user_id": "123"}

    result1 = cache.check_and_add("user.signup", payload1, "event-123")
    result2 = cache.check_and_add("user.signup", payload2, "event-456")

    assert result1 is None
    assert result2 == "event-123"


def test_cleanup_expired_entries():
    """Test expired entries are cleaned up."""
    cache = DeduplicationCache(window_seconds=1)

    # Add event
    cache.check_and_add("test.event", {"data": "test"}, "event-123")
    assert len(cache._cache) == 1

    # Wait for expiration
    time.sleep(1.1)

    # Trigger cleanup by checking new event
    cache.check_and_add("test.event2", {"data": "test2"}, "event-456")

    # Old entry should be removed
    assert len(cache._cache) == 1

    # Original event should not be found (expired)
    result = cache.check_and_add(
        "test.event", {"data": "test"}, "event-789"
    )
    assert result is None  # Not a duplicate anymore


def test_clear_cache():
    """Test clearing the cache."""
    cache = DeduplicationCache()

    cache.check_and_add("event1", {"data": "1"}, "id-1")
    cache.check_and_add("event2", {"data": "2"}, "id-2")
    assert len(cache._cache) == 2

    cache.clear()
    assert len(cache._cache) == 0


def test_multiple_different_events():
    """Test cache handles multiple different events."""
    cache = DeduplicationCache()

    # Add different events
    for i in range(5):
        result = cache.check_and_add(
            f"event.{i}", {"index": i}, f"event-{i}"
        )
        assert result is None

    assert len(cache._cache) == 5


def test_expiry_time_calculation():
    """Test expiry time is set correctly."""
    cache = DeduplicationCache(window_seconds=300)

    with patch("time.time", return_value=1000.0):
        cache.check_and_add("test.event", {"data": "test"}, "event-123")

        # Check expiry is set to now + window_seconds
        for _, (_, expiry) in cache._cache.items():
            assert expiry == 1300.0  # 1000 + 300
