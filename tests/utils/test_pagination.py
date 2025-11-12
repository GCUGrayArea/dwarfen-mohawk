"""Tests for pagination utilities and cursor handling."""

import json

import pytest


def test_cursor_encoding_decoding():
    """Test cursor can be encoded and decoded correctly."""
    cursor_data = {"event_id": "test-123", "timestamp": "2025-11-11T12:00:00Z"}

    # Encode
    cursor = json.dumps(cursor_data)

    # Decode
    decoded = json.loads(cursor)

    assert decoded == cursor_data
    assert decoded["event_id"] == "test-123"
    assert decoded["timestamp"] == "2025-11-11T12:00:00Z"


def test_cursor_with_special_characters():
    """Test cursor with special characters in event_id."""
    cursor_data = {
        "event_id": "test-!@#$%^&*()_+-=[]{}|;:',.<>?",
        "timestamp": "2025-11-11T12:00:00Z",
    }

    cursor = json.dumps(cursor_data)
    decoded = json.loads(cursor)

    assert decoded == cursor_data


def test_cursor_with_unicode_characters():
    """Test cursor with unicode characters."""
    cursor_data = {
        "event_id": "test-unicode-\u00e9\u00e8\u00ea\u4e2d\u6587",
        "timestamp": "2025-11-11T12:00:00Z",
    }

    cursor = json.dumps(cursor_data)
    decoded = json.loads(cursor)

    assert decoded == cursor_data


def test_cursor_with_very_long_event_id():
    """Test cursor with very long event_id (UUID is 36 chars, test longer)."""
    long_id = "a" * 500  # Very long ID
    cursor_data = {"event_id": long_id, "timestamp": "2025-11-11T12:00:00Z"}

    cursor = json.dumps(cursor_data)
    decoded = json.loads(cursor)

    assert decoded == cursor_data
    assert len(decoded["event_id"]) == 500


def test_invalid_cursor_empty_string():
    """Test handling of empty cursor string."""
    cursor = ""

    with pytest.raises(json.JSONDecodeError):
        json.loads(cursor)


def test_invalid_cursor_not_json():
    """Test handling of non-JSON cursor."""
    cursor = "not-valid-json"

    with pytest.raises(json.JSONDecodeError):
        json.loads(cursor)


def test_invalid_cursor_incomplete_json():
    """Test handling of incomplete JSON cursor."""
    cursor = '{"event_id": "test"'  # Missing closing brace

    with pytest.raises(json.JSONDecodeError):
        json.loads(cursor)


def test_invalid_cursor_null():
    """Test handling of null as cursor."""
    cursor = "null"

    # This is valid JSON but not a valid cursor object
    decoded = json.loads(cursor)
    assert decoded is None


def test_invalid_cursor_array():
    """Test handling of array as cursor instead of object."""
    cursor = '["event_id", "timestamp"]'

    decoded = json.loads(cursor)
    assert isinstance(decoded, list)
    # Caller should validate it's a dict


def test_cursor_missing_required_fields():
    """Test cursor with missing required fields."""
    # Missing timestamp
    cursor_data = {"event_id": "test-123"}
    cursor = json.dumps(cursor_data)
    decoded = json.loads(cursor)

    # Decoding succeeds, but missing fields should be caught by caller
    assert "timestamp" not in decoded


def test_cursor_with_extra_fields():
    """Test cursor with extra fields is handled gracefully."""
    cursor_data = {
        "event_id": "test-123",
        "timestamp": "2025-11-11T12:00:00Z",
        "extra_field": "should_be_ignored",
        "another_field": 42,
    }

    cursor = json.dumps(cursor_data)
    decoded = json.loads(cursor)

    assert decoded == cursor_data
    assert decoded["event_id"] == "test-123"


def test_cursor_with_numeric_values():
    """Test cursor containing numeric values."""
    cursor_data = {
        "event_id": "test-123",
        "timestamp": "2025-11-11T12:00:00Z",
        "count": 100,
    }

    cursor = json.dumps(cursor_data)
    decoded = json.loads(cursor)

    assert decoded == cursor_data
    assert decoded["count"] == 100


def test_cursor_with_nested_objects():
    """Test cursor with nested objects (edge case)."""
    cursor_data = {
        "event_id": "test-123",
        "timestamp": "2025-11-11T12:00:00Z",
        "metadata": {"nested": {"deeply": "nested"}},
    }

    cursor = json.dumps(cursor_data)
    decoded = json.loads(cursor)

    assert decoded == cursor_data


def test_cursor_roundtrip_preserves_data():
    """Test multiple encode/decode cycles preserve data."""
    original_data = {"event_id": "test-456", "timestamp": "2025-11-11T13:00:00Z"}

    # Multiple roundtrips
    data = original_data
    for _ in range(5):
        cursor = json.dumps(data)
        data = json.loads(cursor)

    assert data == original_data


def test_cursor_with_empty_event_id():
    """Test cursor with empty event_id string."""
    cursor_data = {"event_id": "", "timestamp": "2025-11-11T12:00:00Z"}

    cursor = json.dumps(cursor_data)
    decoded = json.loads(cursor)

    assert decoded == cursor_data
    assert decoded["event_id"] == ""


def test_cursor_with_whitespace_only_event_id():
    """Test cursor with whitespace-only event_id."""
    cursor_data = {"event_id": "   ", "timestamp": "2025-11-11T12:00:00Z"}

    cursor = json.dumps(cursor_data)
    decoded = json.loads(cursor)

    assert decoded == cursor_data


def test_cursor_encoding_is_deterministic():
    """Test that cursor encoding is deterministic for same data."""
    cursor_data = {"event_id": "test-123", "timestamp": "2025-11-11T12:00:00Z"}

    cursor1 = json.dumps(cursor_data, sort_keys=True)
    cursor2 = json.dumps(cursor_data, sort_keys=True)

    assert cursor1 == cursor2


def test_cursor_field_order_independence():
    """Test cursor works regardless of field order in JSON."""
    cursor1 = '{"event_id": "test", "timestamp": "2025-11-11T12:00:00Z"}'
    cursor2 = '{"timestamp": "2025-11-11T12:00:00Z", "event_id": "test"}'

    decoded1 = json.loads(cursor1)
    decoded2 = json.loads(cursor2)

    # Content should be same regardless of order
    assert decoded1 == decoded2


def test_large_cursor_object():
    """Test handling of very large cursor object."""
    # Create large cursor with many fields
    cursor_data = {
        "event_id": "test-123",
        "timestamp": "2025-11-11T12:00:00Z",
    }

    # Add many extra fields
    for i in range(100):
        cursor_data[f"field_{i}"] = f"value_{i}"

    cursor = json.dumps(cursor_data)
    decoded = json.loads(cursor)

    assert decoded == cursor_data
    assert len(decoded) == 102  # 2 required + 100 extra
