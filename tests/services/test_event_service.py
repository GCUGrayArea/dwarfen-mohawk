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
