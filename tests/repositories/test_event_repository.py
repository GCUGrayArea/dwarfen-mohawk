"""Unit tests for EventRepository."""

from datetime import datetime
from uuid import uuid4

import pytest
from moto import mock_aws

from src.models.event import Event
from src.repositories.event_repository import EventRepository


@pytest.fixture
def event_data() -> dict:
    """Create test event data."""
    return {
        "event_id": str(uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": "test.event",
        "payload": {"test": "data"},
        "source": "test-suite",
        "metadata": {"version": "1.0"},
        "delivered": False,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


@pytest.fixture
async def repository() -> EventRepository:
    """Create EventRepository instance."""
    return EventRepository()


@pytest.fixture
async def setup_dynamodb():
    """Set up mock DynamoDB for testing."""
    with mock_aws():
        # Import after mock is active
        import aioboto3

        session = aioboto3.Session()
        async with session.resource("dynamodb", region_name="us-east-1") as dynamodb:
            # Create events table
            table = await dynamodb.create_table(
                TableName="zapier-events",
                KeySchema=[
                    {"AttributeName": "event_id", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {
                        "AttributeName": "event_id",
                        "AttributeType": "S",
                    },
                    {
                        "AttributeName": "timestamp",
                        "AttributeType": "S",
                    },
                    {"AttributeName": "delivered", "AttributeType": "N"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "DeliveredIndex",
                        "KeySchema": [
                            {
                                "AttributeName": "delivered",
                                "KeyType": "HASH",
                            },
                            {
                                "AttributeName": "timestamp",
                                "KeyType": "RANGE",
                            },
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 1,
                            "WriteCapacityUnits": 1,
                        },
                    }
                ],
                BillingMode="PROVISIONED",
                ProvisionedThroughput={
                    "ReadCapacityUnits": 1,
                    "WriteCapacityUnits": 1,
                },
            )
            await table.wait_until_exists()
            yield


@pytest.mark.asyncio
async def test_create_event(
    setup_dynamodb, repository: EventRepository, event_data: dict
) -> None:
    """Test creating an event."""
    event = Event(**event_data)
    result = await repository.create(event)

    assert result.event_id == event.event_id
    assert result.timestamp == event.timestamp
    assert result.event_type == event.event_type


@pytest.mark.asyncio
async def test_get_by_id(
    setup_dynamodb, repository: EventRepository, event_data: dict
) -> None:
    """Test retrieving an event by ID."""
    event = Event(**event_data)
    await repository.create(event)

    result = await repository.get_by_id(event.event_id, event.timestamp)

    assert result is not None
    assert result.event_id == event.event_id
    assert result.payload == event.payload


@pytest.mark.asyncio
async def test_get_by_id_not_found(setup_dynamodb, repository: EventRepository) -> None:
    """Test retrieving non-existent event."""
    result = await repository.get_by_id("nonexistent", "2025-01-01T00:00:00Z")

    assert result is None


@pytest.mark.asyncio
async def test_mark_delivered(
    setup_dynamodb, repository: EventRepository, event_data: dict
) -> None:
    """Test marking an event as delivered."""
    event = Event(**event_data)
    await repository.create(event)

    result = await repository.mark_delivered(event.event_id, event.timestamp)

    assert result is not None
    assert result.delivered is True
    assert result.ttl is not None


# Error Scenario Tests


@pytest.mark.asyncio
async def test_mark_delivered_nonexistent_event(
    setup_dynamodb, repository: EventRepository
) -> None:
    """Test marking non-existent event as delivered returns None."""
    result = await repository.mark_delivered("nonexistent-id", "2025-11-11T12:00:00Z")

    assert result is None


@pytest.mark.asyncio
async def test_create_with_malformed_data_raises_error() -> None:
    """Test creating event with invalid data raises error."""
    from pydantic import ValidationError

    # Missing required fields
    with pytest.raises(ValidationError):
        Event(
            event_id="test-id",
            # Missing timestamp, event_type, payload, etc.
        )


@pytest.mark.asyncio
async def test_list_undelivered_empty_table(
    setup_dynamodb, repository: EventRepository
) -> None:
    """Test listing undelivered events from empty table."""
    events, next_key = await repository.list_undelivered()

    assert events == []
    assert next_key is None


@pytest.mark.asyncio
async def test_list_undelivered_with_invalid_cursor(
    setup_dynamodb, repository: EventRepository
) -> None:
    """Test list_undelivered handles invalid cursor gracefully."""
    # Invalid cursor with wrong structure
    invalid_cursor = {"invalid": "structure"}

    # Should handle gracefully (DynamoDB will ignore invalid cursor)
    events, next_key = await repository.list_undelivered(
        last_evaluated_key=invalid_cursor
    )

    # Should return results from beginning
    assert isinstance(events, list)


@pytest.mark.asyncio
async def test_get_by_id_with_empty_strings(
    setup_dynamodb, repository: EventRepository
) -> None:
    """Test get_by_id with empty string parameters."""
    result = await repository.get_by_id("", "")

    assert result is None


@pytest.mark.asyncio
async def test_create_multiple_events_same_type(
    setup_dynamodb, repository: EventRepository, event_data: dict
) -> None:
    """Test creating multiple events of same type."""
    # Create first event
    event1 = Event(**event_data)
    await repository.create(event1)

    # Create second event with same type but different ID
    event_data2 = event_data.copy()
    event_data2["event_id"] = str(uuid4())
    event_data2["timestamp"] = datetime.utcnow().isoformat() + "Z"
    event2 = Event(**event_data2)
    await repository.create(event2)

    # Both should be retrievable
    retrieved1 = await repository.get_by_id(event1.event_id, event1.timestamp)
    retrieved2 = await repository.get_by_id(event2.event_id, event2.timestamp)

    assert retrieved1 is not None
    assert retrieved2 is not None
    assert retrieved1.event_id != retrieved2.event_id


@pytest.mark.asyncio
async def test_mark_delivered_idempotent(
    setup_dynamodb, repository: EventRepository, event_data: dict
) -> None:
    """Test marking event as delivered multiple times (idempotency)."""
    event = Event(**event_data)
    await repository.create(event)

    # Mark as delivered first time
    result1 = await repository.mark_delivered(event.event_id, event.timestamp)
    assert result1 is not None
    assert result1.delivered is True

    # Mark as delivered second time (idempotent)
    result2 = await repository.mark_delivered(event.event_id, event.timestamp)
    assert result2 is not None
    assert result2.delivered is True


@pytest.mark.asyncio
async def test_list_undelivered_excludes_delivered_events(
    setup_dynamodb, repository: EventRepository, event_data: dict
) -> None:
    """Test list_undelivered excludes events marked as delivered."""
    # Create first event (undelivered)
    event1 = Event(**event_data)
    await repository.create(event1)

    # Create second event and mark as delivered
    event_data2 = event_data.copy()
    event_data2["event_id"] = str(uuid4())
    event_data2["timestamp"] = datetime.utcnow().isoformat() + "Z"
    event2 = Event(**event_data2)
    await repository.create(event2)
    await repository.mark_delivered(event2.event_id, event2.timestamp)

    # List undelivered should only return first event
    events, _ = await repository.list_undelivered()

    assert len(events) == 1
    assert events[0].event_id == event1.event_id


@pytest.mark.asyncio
async def test_create_with_very_large_payload(
    setup_dynamodb, repository: EventRepository, event_data: dict
) -> None:
    """Test creating event with very large payload near DynamoDB item limit."""
    # DynamoDB item size limit is 400KB
    # Create large but valid payload (256KB as per our validation)
    target_size = 250 * 1024  # 250KB to be safe
    large_value = "x" * target_size

    event_data["payload"] = {"large_field": large_value}
    event = Event(**event_data)

    # Should succeed with large payload
    created = await repository.create(event)
    assert created is not None

    # Should be retrievable
    retrieved = await repository.get_by_id(event.event_id, event.timestamp)
    assert retrieved is not None
    assert len(retrieved.payload["large_field"]) == target_size


@pytest.mark.asyncio
async def test_list_undelivered_pagination_boundary(
    setup_dynamodb, repository: EventRepository, event_data: dict
) -> None:
    """Test pagination boundary when result count equals limit."""
    # Create exactly 5 events
    for i in range(5):
        event_data_copy = event_data.copy()
        event_data_copy["event_id"] = str(uuid4())
        event_data_copy["timestamp"] = datetime.utcnow().isoformat() + f"_{i:03d}" + "Z"
        event = Event(**event_data_copy)
        await repository.create(event)

    # Request exactly 5 (same as count)
    events, next_key = await repository.list_undelivered(limit=5)

    assert len(events) == 5
    # next_key should be None (no more results)
    assert next_key is None


@pytest.mark.asyncio
async def test_deserialize_event_handles_missing_optional_fields(
    setup_dynamodb, repository: EventRepository
) -> None:
    """Test _deserialize_event handles missing optional fields."""
    # Create event with minimal required fields
    minimal_event_data = {
        "event_id": str(uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": "test.minimal",
        "payload": {"test": "data"},
        "delivered": False,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }

    event = Event(**minimal_event_data)
    await repository.create(event)

    retrieved = await repository.get_by_id(event.event_id, event.timestamp)

    assert retrieved is not None
    assert retrieved.source is None
    assert retrieved.metadata is None
