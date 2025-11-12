"""Tests for EventService."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.models.event import Event
from src.schemas.event import CreateEventRequest
from src.services.event_service import EventService
from src.utils.deduplication import DeduplicationCache


@pytest.fixture
def mock_repository():
    """Create mock EventRepository."""
    repository = AsyncMock()
    return repository


@pytest.fixture
def mock_dedup_cache():
    """Create mock DeduplicationCache."""
    cache = Mock(spec=DeduplicationCache)
    cache.check_and_add = Mock(return_value=None)
    return cache


@pytest.fixture
def event_service(mock_repository, mock_dedup_cache):
    """Create EventService with mocked dependencies."""
    return EventService(repository=mock_repository, dedup_cache=mock_dedup_cache)


@pytest.mark.asyncio
async def test_ingest_new_event(event_service, mock_repository):
    """Test ingesting a new event."""
    request = CreateEventRequest(
        event_type="user.signup",
        payload={"user_id": "123", "email": "test@example.com"},
        source="web-app",
    )

    with (
        patch("src.services.event_service.uuid.uuid4") as mock_uuid,
        patch("src.services.event_service.datetime") as mock_datetime,
    ):
        mock_uuid.return_value = Mock(__str__=Mock(return_value="test-uuid-123"))
        mock_datetime.utcnow.return_value.isoformat.return_value = "2025-11-11T12:00:00"

        response = await event_service.ingest(request)

    assert response.status == "accepted"
    assert response.event_id == "test-uuid-123"
    assert response.timestamp == "2025-11-11T12:00:00Z"
    assert response.message == "Event successfully ingested"

    # Verify repository was called
    mock_repository.create.assert_called_once()
    created_event = mock_repository.create.call_args[0][0]
    assert created_event.event_id == "test-uuid-123"
    assert created_event.event_type == "user.signup"
    assert created_event.delivered is False


@pytest.mark.asyncio
async def test_ingest_duplicate_event(event_service, mock_repository, mock_dedup_cache):
    """Test ingesting a duplicate event."""
    request = CreateEventRequest(
        event_type="user.signup",
        payload={"user_id": "123"},
    )

    # Mock dedup cache to return existing event ID
    mock_dedup_cache.check_and_add.return_value = "existing-uuid-456"

    response = await event_service.ingest(request)

    assert response.status == "accepted"
    assert response.event_id == "existing-uuid-456"
    assert "duplicate detected" in response.message.lower()

    # Repository should NOT be called for duplicates
    mock_repository.create.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_with_metadata(event_service, mock_repository):
    """Test ingesting event with optional metadata."""
    request = CreateEventRequest(
        event_type="order.placed",
        payload={"order_id": "ORD-123"},
        source="mobile-app",
        metadata={"ip": "192.168.1.1", "user_agent": "iOS"},
    )

    response = await event_service.ingest(request)

    assert response.status == "accepted"
    mock_repository.create.assert_called_once()

    created_event = mock_repository.create.call_args[0][0]
    assert created_event.source == "mobile-app"
    assert created_event.metadata == {
        "ip": "192.168.1.1",
        "user_agent": "iOS",
    }


@pytest.mark.asyncio
async def test_get_existing_event(event_service, mock_repository):
    """Test retrieving an existing event."""
    mock_event = Event(
        event_id="event-123",
        timestamp="2025-11-11T12:00:00Z",
        event_type="user.login",
        payload={"user_id": "456"},
        source="web-app",
        metadata=None,
        delivered=False,
        created_at="2025-11-11T12:00:00Z",
        updated_at="2025-11-11T12:00:00Z",
    )
    mock_repository.get_by_id.return_value = mock_event

    response = await event_service.get("event-123", "2025-11-11T12:00:00Z")

    assert response is not None
    assert response.status == "success"
    assert response.event_id == "event-123"
    assert response.event_type == "user.login"
    assert response.payload == {"user_id": "456"}
    assert response.delivered is False

    mock_repository.get_by_id.assert_called_once_with(
        "event-123", "2025-11-11T12:00:00Z"
    )


@pytest.mark.asyncio
async def test_get_nonexistent_event(event_service, mock_repository):
    """Test retrieving non-existent event returns None."""
    mock_repository.get_by_id.return_value = None

    response = await event_service.get("nonexistent", "2025-11-11T12:00:00Z")

    assert response is None


@pytest.mark.asyncio
async def test_list_inbox_default_params(event_service, mock_repository):
    """Test listing inbox with default parameters."""
    mock_events = [
        Event(
            event_id=f"event-{i}",
            timestamp=f"2025-11-11T12:0{i}:00Z",
            event_type="test.event",
            payload={"index": i},
            source=None,
            metadata=None,
            delivered=False,
            created_at=f"2025-11-11T12:0{i}:00Z",
            updated_at=f"2025-11-11T12:0{i}:00Z",
        )
        for i in range(3)
    ]
    mock_repository.list_undelivered.return_value = (
        mock_events,
        None,
    )

    response = await event_service.list_inbox()

    assert len(response.events) == 3
    assert response.pagination.has_more is False
    assert response.pagination.next_cursor is None

    mock_repository.list_undelivered.assert_called_once_with(
        limit=50, last_evaluated_key=None
    )


@pytest.mark.asyncio
async def test_list_inbox_with_pagination(event_service, mock_repository):
    """Test listing inbox with pagination cursor."""
    mock_events = [
        Event(
            event_id="event-1",
            timestamp="2025-11-11T12:00:00Z",
            event_type="test.event",
            payload={"data": "test"},
            source=None,
            metadata=None,
            delivered=False,
            created_at="2025-11-11T12:00:00Z",
            updated_at="2025-11-11T12:00:00Z",
        )
    ]
    next_key = {"event_id": "event-1", "timestamp": "2025-11-11T12:00:00Z"}
    mock_repository.list_undelivered.return_value = (
        mock_events,
        next_key,
    )

    response = await event_service.list_inbox(limit=10)

    assert len(response.events) == 1
    assert response.pagination.has_more is True
    assert response.pagination.next_cursor is not None

    # Test using returned cursor
    import json

    cursor = response.pagination.next_cursor
    decoded = json.loads(cursor)
    assert decoded == next_key


@pytest.mark.asyncio
async def test_list_inbox_limit_clamping(event_service, mock_repository):
    """Test inbox limit is clamped to valid range."""
    mock_repository.list_undelivered.return_value = ([], None)

    # Test limit too high
    await event_service.list_inbox(limit=500)
    mock_repository.list_undelivered.assert_called_with(
        limit=200, last_evaluated_key=None
    )

    # Test limit too low
    await event_service.list_inbox(limit=0)
    mock_repository.list_undelivered.assert_called_with(
        limit=1, last_evaluated_key=None
    )


@pytest.mark.asyncio
async def test_list_inbox_with_cursor(event_service, mock_repository):
    """Test listing inbox with cursor parameter."""
    import json

    last_key = {"event_id": "last-event", "timestamp": "2025-11-11T12:00:00Z"}
    cursor = json.dumps(last_key)

    mock_repository.list_undelivered.return_value = ([], None)

    await event_service.list_inbox(cursor=cursor)

    mock_repository.list_undelivered.assert_called_with(
        limit=50, last_evaluated_key=last_key
    )


@pytest.mark.asyncio
async def test_list_inbox_invalid_cursor(event_service, mock_repository):
    """Test invalid cursor is handled gracefully."""
    mock_repository.list_undelivered.return_value = ([], None)

    # Invalid JSON cursor
    await event_service.list_inbox(cursor="invalid-cursor")

    # Should start from beginning (None)
    mock_repository.list_undelivered.assert_called_with(
        limit=50, last_evaluated_key=None
    )


@pytest.mark.asyncio
async def test_mark_delivered_success(event_service, mock_repository):
    """Test marking event as delivered successfully."""
    mock_event = Event(
        event_id="event-123",
        timestamp="2025-11-11T12:00:00Z",
        event_type="test.event",
        payload={},
        source=None,
        metadata=None,
        delivered=True,
        created_at="2025-11-11T12:00:00Z",
        updated_at="2025-11-11T12:01:00Z",
    )
    mock_repository.mark_delivered.return_value = mock_event

    result = await event_service.mark_delivered("event-123", "2025-11-11T12:00:00Z")

    assert result is True
    mock_repository.mark_delivered.assert_called_once_with(
        "event-123", "2025-11-11T12:00:00Z"
    )


@pytest.mark.asyncio
async def test_mark_delivered_not_found(event_service, mock_repository):
    """Test marking non-existent event returns False."""
    mock_repository.mark_delivered.return_value = None

    result = await event_service.mark_delivered("nonexistent", "2025-11-11T12:00:00Z")

    assert result is False


# Edge Case Tests


@pytest.mark.asyncio
async def test_ingest_event_type_single_char(event_service, mock_repository):
    """Test event_type with single character (minimum valid length)."""
    request = CreateEventRequest(
        event_type="a",
        payload={"test": "data"},
    )

    response = await event_service.ingest(request)

    assert response.status == "accepted"
    assert response.event_id is not None
    mock_repository.create.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_event_type_max_length(event_service, mock_repository):
    """Test event_type with exactly 255 characters (maximum valid length)."""
    request = CreateEventRequest(
        event_type="a" * 255,
        payload={"test": "data"},
    )

    response = await event_service.ingest(request)

    assert response.status == "accepted"
    assert response.event_id is not None
    mock_repository.create.assert_called_once()
    created_event = mock_repository.create.call_args[0][0]
    assert len(created_event.event_type) == 255


def test_ingest_event_type_empty_raises_validation_error():
    """Test event_type with empty string raises ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        CreateEventRequest(
            event_type="",
            payload={"test": "data"},
        )

    assert "event_type" in str(exc_info.value).lower()
    assert "at least 1 character" in str(exc_info.value).lower()


def test_ingest_event_type_too_long_raises_validation_error():
    """Test event_type with 256 characters raises ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        CreateEventRequest(
            event_type="a" * 256,
            payload={"test": "data"},
        )

    assert "event_type" in str(exc_info.value).lower()
    assert "at most 255 characters" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_ingest_payload_exactly_256kb(event_service, mock_repository):
    """Test payload at exactly 256KB (should succeed)."""
    # Calculate size to get exactly 256KB when JSON-encoded
    # Account for JSON structure: {"key": "value"}
    target_size = 256 * 1024
    # Subtract overhead for JSON structure
    overhead = len('{"data":""}')
    value_size = target_size - overhead - 1  # Subtract 1 more for safety

    large_payload = {"data": "x" * value_size}

    request = CreateEventRequest(
        event_type="test.large",
        payload=large_payload,
    )

    response = await event_service.ingest(request)

    assert response.status == "accepted"
    assert response.event_id is not None
    mock_repository.create.assert_called_once()


def test_ingest_payload_exceeds_256kb_raises_validation_error():
    """Test payload exceeding 256KB raises ValidationError."""
    from pydantic import ValidationError

    # Create payload larger than 256KB
    target_size = 257 * 1024
    overhead = len('{"data":""}')
    value_size = target_size - overhead

    large_payload = {"data": "x" * value_size}

    with pytest.raises(ValidationError) as exc_info:
        CreateEventRequest(
            event_type="test.toolarge",
            payload=large_payload,
        )

    assert "payload" in str(exc_info.value).lower()
    assert "exceeds maximum" in str(exc_info.value).lower()


def test_ingest_payload_at_255kb_succeeds():
    """Test payload at 255KB (should succeed)."""
    target_size = 255 * 1024
    overhead = len('{"data":""}')
    value_size = target_size - overhead

    large_payload = {"data": "x" * value_size}

    # Should not raise
    request = CreateEventRequest(
        event_type="test.large",
        payload=large_payload,
    )

    assert request.event_type == "test.large"
    assert len(request.payload["data"]) > 0


@pytest.mark.asyncio
async def test_ingest_empty_payload_succeeds(event_service, mock_repository):
    """Test ingesting event with empty payload dictionary."""
    request = CreateEventRequest(
        event_type="test.empty",
        payload={},
    )

    response = await event_service.ingest(request)

    assert response.status == "accepted"
    assert response.event_id is not None
    mock_repository.create.assert_called_once()
    created_event = mock_repository.create.call_args[0][0]
    assert created_event.payload == {}


@pytest.mark.asyncio
async def test_ingest_complex_nested_payload(event_service, mock_repository):
    """Test ingesting event with deeply nested payload."""
    complex_payload = {
        "level1": {
            "level2": {
                "level3": {
                    "level4": {"data": "nested", "array": [1, 2, 3, {"key": "value"}]}
                }
            }
        },
        "array": [1, 2, 3, [4, 5, [6, 7]]],
        "mixed": [{"a": 1}, {"b": 2}, [3, 4]],
    }

    request = CreateEventRequest(
        event_type="test.nested",
        payload=complex_payload,
    )

    response = await event_service.ingest(request)

    assert response.status == "accepted"
    mock_repository.create.assert_called_once()
    created_event = mock_repository.create.call_args[0][0]
    assert created_event.payload == complex_payload


@pytest.mark.asyncio
async def test_list_inbox_empty(event_service, mock_repository):
    """Test listing inbox when no events exist."""
    mock_repository.list_undelivered.return_value = ([], None)

    response = await event_service.list_inbox()

    assert len(response.events) == 0
    assert response.pagination.has_more is False
    assert response.pagination.next_cursor is None
    assert response.pagination.total_undelivered == 0


@pytest.mark.asyncio
async def test_list_inbox_exactly_at_limit(event_service, mock_repository):
    """Test listing inbox when result count equals limit."""
    mock_events = [
        Event(
            event_id=f"event-{i}",
            timestamp=f"2025-11-11T12:{i:02d}:00Z",
            event_type="test.event",
            payload={"index": i},
            source=None,
            metadata=None,
            delivered=False,
            created_at=f"2025-11-11T12:{i:02d}:00Z",
            updated_at=f"2025-11-11T12:{i:02d}:00Z",
        )
        for i in range(50)
    ]
    mock_repository.list_undelivered.return_value = (mock_events, None)

    response = await event_service.list_inbox(limit=50)

    assert len(response.events) == 50
    assert response.pagination.has_more is False


@pytest.mark.asyncio
async def test_list_inbox_cursor_with_special_characters(
    event_service, mock_repository
):
    """Test cursor with special characters is handled properly."""
    import json

    # Create cursor with special characters
    cursor_data = {
        "event_id": "test-id-with-!@#$%",
        "timestamp": "2025-11-11T12:00:00Z",
    }
    cursor = json.dumps(cursor_data)

    mock_repository.list_undelivered.return_value = ([], None)

    await event_service.list_inbox(cursor=cursor)

    # Should decode cursor correctly
    mock_repository.list_undelivered.assert_called_with(
        limit=50, last_evaluated_key=cursor_data
    )


@pytest.mark.asyncio
async def test_list_inbox_malformed_cursor_starts_from_beginning(
    event_service, mock_repository
):
    """Test malformed cursor falls back to starting from beginning."""
    mock_repository.list_undelivered.return_value = ([], None)

    # Various malformed cursors that should all fall back to None
    malformed_cursors = [
        "not-json",
        "{invalid json",
        '{"incomplete":',
    ]

    for cursor in malformed_cursors:
        mock_repository.list_undelivered.reset_mock()  # Reset mock between calls
        await event_service.list_inbox(cursor=cursor)
        # Should fall back to None (start from beginning)
        mock_repository.list_undelivered.assert_called_once_with(
            limit=50, last_evaluated_key=None
        )

    # Note: "null" and "123" are valid JSON and will be parsed (though may fail later)
    # So they're not true malformed cursor tests
