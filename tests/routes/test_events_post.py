"""Integration tests for POST /events endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from src.auth.api_key import hash_api_key
from src.main import app
from src.models.api_key import ApiKey


@pytest.fixture
def valid_api_key():
    """Create a valid API key for testing."""
    return "test_api_key_12345678901234567890123456789012"


@pytest.fixture
def mock_api_key_model(valid_api_key):
    """Create mock ApiKey model."""
    return ApiKey(
        key_id="test-key-id-123",
        key_hash=hash_api_key(valid_api_key),
        status="active",
        rate_limit=100,
        created_at="2025-11-11T00:00:00Z",
    )


@pytest.fixture
def valid_event_request():
    """Create valid event request payload."""
    return {
        "event_type": "user.signup",
        "payload": {"user_id": "123", "email": "test@example.com"},
        "source": "web-app",
        "metadata": {"ip": "192.168.1.1"},
    }


@pytest.mark.asyncio
async def test_create_event_success(
    valid_api_key, mock_api_key_model, valid_event_request
):
    """Test successful event creation."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch("src.services.event_service.EventRepository") as mock_repo_class,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        # Setup mocks
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=valid_event_request,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "accepted"
        assert "event_id" in data
        assert "timestamp" in data
        assert data["message"] == "Event successfully ingested"


@pytest.mark.asyncio
async def test_create_event_missing_auth():
    """Test event creation without authentication header."""
    valid_event_request = {
        "event_type": "user.signup",
        "payload": {"user_id": "123"},
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/events", json=valid_event_request)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_create_event_invalid_api_key():
    """Test event creation with invalid API key."""
    valid_event_request = {
        "event_type": "user.signup",
        "payload": {"user_id": "123"},
    }

    with patch("src.auth.dependencies.verify_key_against_all") as mock_verify:
        mock_verify.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=valid_event_request,
                headers={"Authorization": "Bearer invalid_key"},
            )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_create_event_revoked_key(valid_api_key, mock_api_key_model):
    """Test event creation with revoked API key."""
    revoked_key = ApiKey(**{**mock_api_key_model.model_dump(), "status": "revoked"})

    valid_event_request = {
        "event_type": "user.signup",
        "payload": {"user_id": "123"},
    }

    with patch("src.auth.dependencies.verify_key_against_all") as mock_verify:
        mock_verify.return_value = revoked_key

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=valid_event_request,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_create_event_missing_required_field(valid_api_key, mock_api_key_model):
    """Test event creation with missing required field."""
    invalid_request = {
        "payload": {"user_id": "123"},
        # event_type is missing
    }

    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=invalid_request,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "validation_errors" in data["details"]


@pytest.mark.asyncio
async def test_create_event_empty_event_type(valid_api_key, mock_api_key_model):
    """Test event creation with empty event_type."""
    invalid_request = {
        "event_type": "",
        "payload": {"user_id": "123"},
    }

    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=invalid_request,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_event_oversized_payload(valid_api_key, mock_api_key_model):
    """Test event creation with oversized payload (> 256KB)."""
    # Create payload > 256KB
    large_data = "x" * (256 * 1024 + 1)
    oversized_request = {
        "event_type": "test.large",
        "payload": {"data": large_data},
    }

    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=oversized_request,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_event_rate_limit_exceeded(
    valid_api_key, mock_api_key_model, valid_event_request
):
    """Test event creation when rate limit is exceeded."""
    from src.exceptions import RateLimitError

    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.side_effect = RateLimitError(
            message="Rate limit exceeded", retry_after=60
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=valid_event_request,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in response.headers


@pytest.mark.asyncio
async def test_create_event_duplicate_detection(
    valid_api_key, mock_api_key_model, valid_event_request
):
    """Test duplicate event detection returns same event ID."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch("src.services.event_service.EventRepository") as mock_repo_class,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
        patch("src.utils.deduplication.DeduplicationCache.check_and_add") as mock_dedup,
    ):
        # Setup mocks
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None
        mock_dedup.return_value = "existing-event-id-123"  # Duplicate detected

        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=valid_event_request,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event_id"] == "existing-event-id-123"
        assert "duplicate detected" in data["message"].lower()

        # Repository create should NOT be called for duplicates
        mock_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_event_malformed_json():
    """Test event creation with malformed JSON."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/events",
            content="{ invalid json }",
            headers={
                "Authorization": "Bearer test_key",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
