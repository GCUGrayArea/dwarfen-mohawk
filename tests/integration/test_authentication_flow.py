"""Integration tests for authentication and rate limiting."""

import asyncio

import pytest
from fastapi import status
from httpx import AsyncClient

from src.auth.api_key import hash_api_key
from src.models.api_key import ApiKey
from src.repositories.api_key_repository import ApiKeyRepository

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authentication_missing_header(
    api_client: AsyncClient,
    dynamodb_tables
):
    """Test that requests without Authorization header return 401."""
    event_data = {
        "event_type": "test.event",
        "payload": {"test": "data"}
    }

    response = await api_client.post(
        "/events",
        json=event_data
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "UNAUTHORIZED"
    assert "authorization" in data["message"].lower()


@pytest.mark.asyncio
async def test_authentication_invalid_format(
    api_client: AsyncClient,
    dynamodb_tables
):
    """Test that malformed Authorization header returns 401."""
    event_data = {
        "event_type": "test.event",
        "payload": {"test": "data"}
    }

    # Missing "Bearer" prefix
    response = await api_client.post(
        "/events",
        json=event_data,
        headers={"Authorization": "invalid_api_key_123"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_authentication_invalid_key(
    api_client: AsyncClient,
    dynamodb_tables
):
    """Test that invalid API key returns 401."""
    event_data = {
        "event_type": "test.event",
        "payload": {"test": "data"}
    }

    response = await api_client.post(
        "/events",
        json=event_data,
        headers={"Authorization": "Bearer nonexistent_key_12345"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_authentication_valid_key(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    dynamodb_tables
):
    """Test that valid API key allows access."""
    event_data = {
        "event_type": "test.event",
        "payload": {"test": "data"}
    }

    response = await api_client.post(
        "/events",
        json=event_data,
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "accepted"


@pytest.mark.asyncio
async def test_authentication_revoked_key(
    api_client: AsyncClient,
    dynamodb_tables
):
    """Test that revoked API key returns 403."""
    # Create a revoked API key
    plaintext_key = "revoked_test_key_1234567890123456"
    key_hash = hash_api_key(plaintext_key)

    revoked_key = ApiKey(
        key_id="revoked-key-001",
        key_hash=key_hash,
        status="revoked",
        rate_limit=100,
        created_at="2025-11-11T00:00:00Z",
    )

    repo = ApiKeyRepository()
    await repo.create(revoked_key)

    event_data = {
        "event_type": "test.event",
        "payload": {"test": "data"}
    }

    response = await api_client.post(
        "/events",
        json=event_data,
        headers={"Authorization": f"Bearer {plaintext_key}"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_authentication_inactive_key(
    api_client: AsyncClient,
    dynamodb_tables
):
    """Test that inactive API key returns 403."""
    # Create an inactive API key
    plaintext_key = "inactive_test_key_1234567890123456"
    key_hash = hash_api_key(plaintext_key)

    inactive_key = ApiKey(
        key_id="inactive-key-001",
        key_hash=key_hash,
        status="inactive",
        rate_limit=100,
        created_at="2025-11-11T00:00:00Z",
    )

    repo = ApiKeyRepository()
    await repo.create(inactive_key)

    event_data = {
        "event_type": "test.event",
        "payload": {"test": "data"}
    }

    response = await api_client.post(
        "/events",
        json=event_data,
        headers={"Authorization": f"Bearer {plaintext_key}"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_rate_limiting_exceed_limit(
    api_client: AsyncClient,
    dynamodb_tables
):
    """
    Test that exceeding rate limit returns 429.

    Creates a key with low rate limit and exceeds it.
    """
    # Create API key with very low rate limit (2 requests/minute)
    plaintext_key = "rate_limit_test_key_12345678901234567"
    key_hash = hash_api_key(plaintext_key)

    limited_key = ApiKey(
        key_id="limited-key-001",
        key_hash=key_hash,
        status="active",
        rate_limit=2,  # Very low limit for testing
        created_at="2025-11-11T00:00:00Z",
    )

    repo = ApiKeyRepository()
    await repo.create(limited_key)

    event_data = {
        "event_type": "test.rate.limit",
        "payload": {"test": "rate_limiting"}
    }

    headers = {"Authorization": f"Bearer {plaintext_key}"}

    # Make first request (should succeed)
    response1 = await api_client.post(
        "/events",
        json=event_data,
        headers=headers
    )
    assert response1.status_code == status.HTTP_200_OK

    # Make second request (should succeed)
    response2 = await api_client.post(
        "/events",
        json=event_data,
        headers=headers
    )
    assert response2.status_code == status.HTTP_200_OK

    # Make third request (should be rate limited)
    response3 = await api_client.post(
        "/events",
        json=event_data,
        headers=headers
    )
    assert response3.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    data = response3.json()
    assert data["status"] == "error"
    assert data["error_code"] == "RATE_LIMIT_EXCEEDED"

    # Verify Retry-After header is present
    assert "Retry-After" in response3.headers
    retry_after = int(response3.headers["Retry-After"])
    assert retry_after > 0


@pytest.mark.asyncio
async def test_rate_limiting_reset_after_window(
    api_client: AsyncClient,
    dynamodb_tables
):
    """
    Test that rate limit resets after time window.

    This test verifies the rate limiter resets after 60 seconds.
    """
    # Create API key with low rate limit
    plaintext_key = "rate_reset_test_key_12345678901234567"
    key_hash = hash_api_key(plaintext_key)

    limited_key = ApiKey(
        key_id="reset-key-001",
        key_hash=key_hash,
        status="active",
        rate_limit=1,  # Only 1 request per minute
        created_at="2025-11-11T00:00:00Z",
    )

    repo = ApiKeyRepository()
    await repo.create(limited_key)

    event_data = {
        "event_type": "test.rate.reset",
        "payload": {"test": "rate_reset"}
    }

    headers = {"Authorization": f"Bearer {plaintext_key}"}

    # Make first request (should succeed)
    response1 = await api_client.post(
        "/events",
        json=event_data,
        headers=headers
    )
    assert response1.status_code == status.HTTP_200_OK

    # Make second request immediately (should fail)
    response2 = await api_client.post(
        "/events",
        json=event_data,
        headers=headers
    )
    assert response2.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # Wait for rate limit window to reset (60 seconds + buffer)
    # Note: In real tests, we'd mock time, but for integration
    # testing we accept this is a slow test
    await asyncio.sleep(61)

    # Make request after window reset (should succeed)
    response3 = await api_client.post(
        "/events",
        json=event_data,
        headers=headers
    )
    assert response3.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_rate_limiting_per_key_isolation(
    api_client: AsyncClient,
    dynamodb_tables
):
    """
    Test that rate limits are isolated per API key.

    Exceeding rate limit for one key doesn't affect another.
    """
    # Create two API keys with low rate limits
    key1_plaintext = "key1_test_12345678901234567890123456"
    key1_hash = hash_api_key(key1_plaintext)

    key1 = ApiKey(
        key_id="isolation-key-001",
        key_hash=key1_hash,
        status="active",
        rate_limit=1,
        created_at="2025-11-11T00:00:00Z",
    )

    key2_plaintext = "key2_test_12345678901234567890123456"
    key2_hash = hash_api_key(key2_plaintext)

    key2 = ApiKey(
        key_id="isolation-key-002",
        key_hash=key2_hash,
        status="active",
        rate_limit=1,
        created_at="2025-11-11T00:00:00Z",
    )

    repo = ApiKeyRepository()
    await repo.create(key1)
    await repo.create(key2)

    event_data = {
        "event_type": "test.isolation",
        "payload": {"test": "isolation"}
    }

    # Exhaust key1's rate limit
    response1 = await api_client.post(
        "/events",
        json=event_data,
        headers={"Authorization": f"Bearer {key1_plaintext}"}
    )
    assert response1.status_code == status.HTTP_200_OK

    # Second request with key1 should fail
    response2 = await api_client.post(
        "/events",
        json=event_data,
        headers={"Authorization": f"Bearer {key1_plaintext}"}
    )
    assert response2.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # Request with key2 should still succeed (independent limit)
    response3 = await api_client.post(
        "/events",
        json=event_data,
        headers={"Authorization": f"Bearer {key2_plaintext}"}
    )
    assert response3.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_authentication_all_endpoints_protected(
    api_client: AsyncClient,
    dynamodb_tables
):
    """Test that all endpoints require authentication."""
    # Test GET /inbox
    inbox_response = await api_client.get("/inbox")
    assert inbox_response.status_code == status.HTTP_401_UNAUTHORIZED

    # Test GET /events/{id}
    get_response = await api_client.get(
        "/events/test-id",
        params={"timestamp": "2025-11-11T00:00:00Z"}
    )
    assert get_response.status_code == status.HTTP_401_UNAUTHORIZED

    # Test DELETE /events/{id}
    delete_response = await api_client.delete(
        "/events/test-id",
        params={"timestamp": "2025-11-11T00:00:00Z"}
    )
    assert delete_response.status_code == status.HTTP_401_UNAUTHORIZED
