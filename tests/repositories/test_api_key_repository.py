"""Unit tests for ApiKeyRepository."""

from datetime import datetime
from uuid import uuid4

import pytest
from moto import mock_aws

from src.models.api_key import ApiKey
from src.repositories.api_key_repository import ApiKeyRepository


@pytest.fixture
def api_key_data() -> dict:
    """Create test API key data."""
    return {
        "key_id": str(uuid4()),
        "key_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/Lew",
        "status": "active",
        "rate_limit": 100,
        "allowed_event_types": None,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "last_used_at": None,
        "description": "Test API key",
    }


@pytest.fixture
async def repository() -> ApiKeyRepository:
    """Create ApiKeyRepository instance."""
    return ApiKeyRepository()


@pytest.fixture
async def setup_dynamodb():
    """Set up mock DynamoDB for testing."""
    with mock_aws():
        # Import after mock is active
        import aioboto3

        session = aioboto3.Session()
        async with session.resource("dynamodb", region_name="us-east-1") as dynamodb:
            # Create API keys table
            table = await dynamodb.create_table(
                TableName="zapier-api-keys",
                KeySchema=[
                    {"AttributeName": "key_id", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "key_id", "AttributeType": "S"},
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
async def test_create_api_key(
    setup_dynamodb,
    repository: ApiKeyRepository,
    api_key_data: dict,
) -> None:
    """Test creating an API key."""
    api_key = ApiKey(**api_key_data)
    result = await repository.create(api_key)

    assert result.key_id == api_key.key_id
    assert result.key_hash == api_key.key_hash
    assert result.status == "active"


@pytest.mark.asyncio
async def test_get_by_id(
    setup_dynamodb,
    repository: ApiKeyRepository,
    api_key_data: dict,
) -> None:
    """Test retrieving an API key by ID."""
    api_key = ApiKey(**api_key_data)
    await repository.create(api_key)

    result = await repository.get_by_id(api_key.key_id)

    assert result is not None
    assert result.key_id == api_key.key_id
    assert result.key_hash == api_key.key_hash


@pytest.mark.asyncio
async def test_get_by_id_not_found(
    setup_dynamodb, repository: ApiKeyRepository
) -> None:
    """Test retrieving non-existent API key."""
    result = await repository.get_by_id("nonexistent-key-id")

    assert result is None


@pytest.mark.asyncio
async def test_get_by_key_hash(
    setup_dynamodb,
    repository: ApiKeyRepository,
    api_key_data: dict,
) -> None:
    """Test retrieving an API key by hash."""
    api_key = ApiKey(**api_key_data)
    await repository.create(api_key)

    result = await repository.get_by_key_hash(api_key.key_hash)

    assert result is not None
    assert result.key_id == api_key.key_id
    assert result.key_hash == api_key.key_hash


@pytest.mark.asyncio
async def test_get_by_key_hash_not_found(
    setup_dynamodb, repository: ApiKeyRepository
) -> None:
    """Test retrieving API key with non-existent hash."""
    result = await repository.get_by_key_hash("nonexistent-hash")

    assert result is None
