"""Pytest fixtures for integration tests with LocalStack DynamoDB."""

import asyncio
import os
from typing import AsyncGenerator, Generator

import aioboto3
import pytest
from botocore.exceptions import ClientError
from httpx import ASGITransport, AsyncClient

from src.auth.api_key import hash_api_key
from src.config import settings
from src.main import app
from src.models.api_key import ApiKey
from src.repositories.api_key_repository import ApiKeyRepository


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def dynamodb_tables() -> AsyncGenerator:
    """
    Create fresh DynamoDB tables for each test.

    This fixture ensures tests run against clean tables
    and cleans up after each test.
    """
    # Use localhost endpoint for integration tests
    # (assumes LocalStack is running on localhost:4566)
    endpoint_url = os.getenv(
        "DYNAMODB_ENDPOINT_URL",
        "http://localhost:4566"
    )

    session = aioboto3.Session()

    async with session.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=endpoint_url,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    ) as dynamodb:
        # Create Events table
        try:
            events_table = await dynamodb.create_table(
                TableName=settings.dynamodb_table_events,
                KeySchema=[
                    {"AttributeName": "event_id", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "event_id", "AttributeType": "S"},
                    {"AttributeName": "timestamp", "AttributeType": "S"},
                    {"AttributeName": "delivered", "AttributeType": "N"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "DeliveredIndex",
                        "KeySchema": [
                            {"AttributeName": "delivered", "KeyType": "HASH"},
                            {"AttributeName": "timestamp", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5,
                        },
                    }
                ],
                BillingMode="PROVISIONED",
                ProvisionedThroughput={
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            )
            await events_table.wait_until_exists()
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceInUseException":
                raise

        # Create API Keys table
        try:
            api_keys_table = await dynamodb.create_table(
                TableName=settings.dynamodb_table_api_keys,
                KeySchema=[
                    {"AttributeName": "key_id", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "key_id", "AttributeType": "S"},
                ],
                BillingMode="PROVISIONED",
                ProvisionedThroughput={
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            )
            await api_keys_table.wait_until_exists()
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceInUseException":
                raise

        yield dynamodb

        # Cleanup: Delete tables after test
        try:
            events_table = await dynamodb.Table(
                settings.dynamodb_table_events
            )
            await events_table.delete()
        except Exception:
            pass

        try:
            api_keys_table = await dynamodb.Table(
                settings.dynamodb_table_api_keys
            )
            await api_keys_table.delete()
        except Exception:
            pass


@pytest.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing API endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def test_api_key(dynamodb_tables) -> str:
    """
    Create and store a valid test API key in DynamoDB.

    Returns the plaintext API key (stored as hash in DB).
    """
    plaintext_key = "test_integration_key_1234567890123456"
    key_hash = hash_api_key(plaintext_key)

    api_key = ApiKey(
        key_id="integration-test-key-001",
        key_hash=key_hash,
        status="active",
        rate_limit=100,
        created_at="2025-11-11T00:00:00Z",
        last_used_at=None,
    )

    repo = ApiKeyRepository()
    await repo.create(api_key)

    return plaintext_key


@pytest.fixture
def auth_headers(test_api_key: str) -> dict[str, str]:
    """Create authorization headers with valid API key."""
    return {"Authorization": f"Bearer {test_api_key}"}
