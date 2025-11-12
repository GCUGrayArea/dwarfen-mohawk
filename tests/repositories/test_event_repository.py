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
