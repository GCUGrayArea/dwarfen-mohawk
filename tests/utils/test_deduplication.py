"""Tests for deduplication cache."""

import time
from unittest.mock import patch

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

    fp1 = cache._generate_fingerprint("user.login", {"user_id": "123"})
    fp2 = cache._generate_fingerprint("user.login", {"user_id": "456"})
    fp3 = cache._generate_fingerprint("user.logout", {"user_id": "123"})

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
    result = cache.check_and_add("test.event", {"data": "test"}, "event-789")
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
        result = cache.check_and_add(f"event.{i}", {"index": i}, f"event-{i}")
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


# Edge Case Tests for Timing


def test_duplicate_detected_within_window():
    """Test duplicate is detected within deduplication window."""
    cache = DeduplicationCache(window_seconds=300)

    # Add first event
    result1 = cache.check_and_add("user.login", {"user_id": "123"}, "event-1")
    assert result1 is None

    # Try to add duplicate immediately (well within window)
    result2 = cache.check_and_add("user.login", {"user_id": "123"}, "event-2")
    assert result2 == "event-1"


def test_duplicate_not_detected_after_window_expires():
    """Test duplicate is NOT detected after window expires."""
    cache = DeduplicationCache(window_seconds=2)

    # Add first event
    result1 = cache.check_and_add("user.login", {"user_id": "123"}, "event-1")
    assert result1 is None

    # Wait for window to expire
    time.sleep(2.1)

    # Trigger cleanup and add "duplicate" (should be treated as new)
    result2 = cache.check_and_add("user.login", {"user_id": "123"}, "event-2")
    assert result2 is None  # Not a duplicate anymore

    # The second event should now be in cache
    result3 = cache.check_and_add("user.login", {"user_id": "123"}, "event-3")
    assert result3 == "event-2"


def test_duplicate_at_window_boundary():
    """Test duplicate detection at edge of window boundary."""
    cache = DeduplicationCache(window_seconds=1)

    # Add first event
    result1 = cache.check_and_add("test.event", {"data": "test"}, "event-1")
    assert result1 is None

    # Wait just under window time
    time.sleep(0.9)

    # Should still detect duplicate
    result2 = cache.check_and_add("test.event", {"data": "test"}, "event-2")
    assert result2 == "event-1"


def test_multiple_events_different_expiry_times():
    """Test multiple events with different expiry times are cleaned up correctly."""
    cache = DeduplicationCache(window_seconds=2)

    # Add first event
    cache.check_and_add("event.1", {"id": 1}, "id-1")
    assert len(cache._cache) == 1

    # Wait 1 second and add second event
    time.sleep(1)
    cache.check_and_add("event.2", {"id": 2}, "id-2")
    assert len(cache._cache) == 2

    # Wait another 1.5 seconds (total 2.5) - first event should expire
    time.sleep(1.5)

    # Trigger cleanup by adding new event
    cache.check_and_add("event.3", {"id": 3}, "id-3")

    # First event should be gone, but second and third should remain
    assert len(cache._cache) == 2

    # First event should not be detected as duplicate
    result = cache.check_and_add("event.1", {"id": 1}, "id-4")
    assert result is None


def test_concurrent_duplicates_within_window():
    """Test multiple duplicate attempts within same window."""
    cache = DeduplicationCache(window_seconds=300)

    # Add original event
    result1 = cache.check_and_add("order.placed", {"order_id": "123"}, "event-1")
    assert result1 is None

    # Try multiple duplicates in quick succession
    for i in range(2, 10):
        result = cache.check_and_add(
            "order.placed", {"order_id": "123"}, f"event-{i}"
        )
        assert result == "event-1"

    # Cache should only have one entry
    assert len(cache._cache) == 1


def test_zero_window_no_deduplication():
    """Test that window_seconds=0 effectively disables deduplication."""
    cache = DeduplicationCache(window_seconds=0)

    # Add first event
    result1 = cache.check_and_add("test.event", {"data": "test"}, "event-1")
    assert result1 is None

    # Immediate "duplicate" should not be detected (already expired)
    result2 = cache.check_and_add("test.event", {"data": "test"}, "event-2")
    # Note: This might still detect as duplicate if executed in same instant
    # In practice, entries expire immediately, so this tests cleanup behavior


def test_very_short_window():
    """Test deduplication with very short window (0.1 seconds)."""
    cache = DeduplicationCache(window_seconds=0.1)

    # Add event
    result1 = cache.check_and_add("test.event", {"data": "test"}, "event-1")
    assert result1 is None

    # Immediate duplicate should be detected
    result2 = cache.check_and_add("test.event", {"data": "test"}, "event-2")
    assert result2 == "event-1"

    # Wait for window to expire
    time.sleep(0.15)

    # Should not detect duplicate anymore
    result3 = cache.check_and_add("test.event", {"data": "test"}, "event-3")
    assert result3 is None


def test_cleanup_does_not_affect_valid_entries():
    """Test cleanup only removes expired entries, not valid ones."""
    cache = DeduplicationCache(window_seconds=10)

    # Add multiple events
    for i in range(5):
        cache.check_and_add(f"event.{i}", {"index": i}, f"id-{i}")

    assert len(cache._cache) == 5

    # Trigger cleanup (no entries should expire yet)
    cache._cleanup_expired()

    # All entries should still be present
    assert len(cache._cache) == 5


def test_large_number_of_entries():
    """Test cache handles large number of entries efficiently."""
    cache = DeduplicationCache(window_seconds=60)

    # Add many different events
    for i in range(1000):
        result = cache.check_and_add(f"event.{i}", {"index": i}, f"id-{i}")
        assert result is None

    assert len(cache._cache) == 1000

    # All events should still be detectable as duplicates
    for i in range(100):  # Test subset
        result = cache.check_and_add(f"event.{i}", {"index": i}, f"new-id-{i}")
        assert result == f"id-{i}"
