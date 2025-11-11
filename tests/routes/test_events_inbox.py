"""Integration tests for GET /inbox endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from src.auth.api_key import hash_api_key
from src.main import app
from src.models.api_key import ApiKey
from src.models.event import Event


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
def sample_events():
    """Create sample undelivered events."""
    return [
        Event(
            event_id="event-1",
            timestamp="2025-11-11T12:00:00Z",
            event_type="user.signup",
            payload={"user_id": "1", "email": "user1@example.com"},
            source="web-app",
            delivered=False,
            created_at="2025-11-11T12:00:00Z",
            updated_at="2025-11-11T12:00:00Z",
        ),
        Event(
            event_id="event-2",
            timestamp="2025-11-11T12:01:00Z",
            event_type="user.login",
            payload={"user_id": "2"},
            source="mobile-app",
            delivered=False,
            created_at="2025-11-11T12:01:00Z",
            updated_at="2025-11-11T12:01:00Z",
        ),
        Event(
            event_id="event-3",
            timestamp="2025-11-11T12:02:00Z",
            event_type="order.created",
            payload={"order_id": "order-123", "amount": 99.99},
            delivered=False,
            created_at="2025-11-11T12:02:00Z",
            updated_at="2025-11-11T12:02:00Z",
        ),
    ]


@pytest.mark.asyncio
async def test_get_inbox_success(
    valid_api_key, mock_api_key_model, sample_events
):
    """Test successful retrieval of inbox events."""
    with patch(
        "src.auth.dependencies.verify_key_against_all"
    ) as mock_verify, patch(
        "src.services.event_service.EventRepository"
    ) as mock_repo_class, patch(
        "src.middleware.rate_limit.rate_limiter.check_rate_limit"
    ) as mock_rate_limit:
        # Setup mocks
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = True

        mock_repo = AsyncMock()
        mock_repo.list_undelivered = AsyncMock(
            return_value=(sample_events, None)
        )
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/events/inbox",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "events" in data
        assert "pagination" in data
        assert len(data["events"]) == 3
        assert data["events"][0]["event_id"] == "event-1"
        assert data["events"][0]["event_type"] == "user.signup"
        assert data["pagination"]["has_more"] is False
        assert data["pagination"]["next_cursor"] is None


@pytest.mark.asyncio
async def test_get_inbox_with_limit(
    valid_api_key, mock_api_key_model, sample_events
):
    """Test inbox retrieval with custom limit."""
    with patch(
        "src.auth.dependencies.verify_key_against_all"
    ) as mock_verify, patch(
        "src.services.event_service.EventRepository"
    ) as mock_repo_class, patch(
        "src.middleware.rate_limit.rate_limiter.check_rate_limit"
    ) as mock_rate_limit:
        # Setup mocks
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = True

        mock_repo = AsyncMock()
        mock_repo.list_undelivered = AsyncMock(
            return_value=(sample_events[:2], {"event_id": "event-2"})
        )
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/events/inbox?limit=2",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["events"]) == 2
        assert data["pagination"]["has_more"] is True
        assert data["pagination"]["next_cursor"] is not None


@pytest.mark.asyncio
async def test_get_inbox_with_cursor(
    valid_api_key, mock_api_key_model, sample_events
):
    """Test inbox pagination with cursor."""
    import json

    cursor = json.dumps({"event_id": "event-2"})

    with patch(
        "src.auth.dependencies.verify_key_against_all"
    ) as mock_verify, patch(
        "src.services.event_service.EventRepository"
    ) as mock_repo_class, patch(
        "src.middleware.rate_limit.rate_limiter.check_rate_limit"
    ) as mock_rate_limit:
        # Setup mocks
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = True

        mock_repo = AsyncMock()
        mock_repo.list_undelivered = AsyncMock(
            return_value=([sample_events[2]], None)
        )
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/events/inbox?cursor={cursor}",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["event_id"] == "event-3"
        assert data["pagination"]["has_more"] is False


@pytest.mark.asyncio
async def test_get_inbox_empty():
    """Test inbox retrieval when no events exist."""
    valid_api_key = "test_api_key_12345678901234567890123456789012"

    with patch(
        "src.auth.dependencies.verify_key_against_all"
    ) as mock_verify, patch(
        "src.services.event_service.EventRepository"
    ) as mock_repo_class, patch(
        "src.middleware.rate_limit.rate_limiter.check_rate_limit"
    ) as mock_rate_limit:
        # Setup mocks
        mock_api_key = ApiKey(
            key_id="test-key-id",
            key_hash=hash_api_key(valid_api_key),
            status="active",
            rate_limit=100,
            created_at="2025-11-11T00:00:00Z",
        )
        mock_verify.return_value = mock_api_key
        mock_rate_limit.return_value = True

        mock_repo = AsyncMock()
        mock_repo.list_undelivered = AsyncMock(return_value=([], None))
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/events/inbox",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["events"] == []
        assert data["pagination"]["has_more"] is False
        assert data["pagination"]["next_cursor"] is None
        assert data["pagination"]["total_undelivered"] == 0


@pytest.mark.asyncio
async def test_get_inbox_missing_auth():
    """Test inbox retrieval without authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/events/inbox")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_get_inbox_invalid_api_key():
    """Test inbox retrieval with invalid API key."""
    invalid_key = "invalid_key_123"

    with patch(
        "src.auth.dependencies.verify_key_against_all"
    ) as mock_verify:
        mock_verify.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/events/inbox",
                headers={"Authorization": f"Bearer {invalid_key}"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_inbox_rate_limit_exceeded(
    valid_api_key, mock_api_key_model
):
    """Test inbox retrieval when rate limit is exceeded."""
    with patch(
        "src.auth.dependencies.verify_key_against_all"
    ) as mock_verify, patch(
        "src.middleware.rate_limit.rate_limiter.check_rate_limit"
    ) as mock_rate_limit:
        # Setup mocks
        from src.exceptions import RateLimitError
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.side_effect = RateLimitError(
            message="Rate limit exceeded",
            retry_after=60
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/events/inbox",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_get_inbox_limit_validation():
    """Test inbox limit parameter validation."""
    valid_api_key = "test_api_key_12345678901234567890123456789012"

    with patch(
        "src.auth.dependencies.verify_key_against_all"
    ) as mock_verify, patch(
        "src.services.event_service.EventRepository"
    ) as mock_repo_class, patch(
        "src.middleware.rate_limit.rate_limiter.check_rate_limit"
    ) as mock_rate_limit:
        # Setup mocks
        mock_api_key = ApiKey(
            key_id="test-key-id",
            key_hash=hash_api_key(valid_api_key),
            status="active",
            rate_limit=100,
            created_at="2025-11-11T00:00:00Z",
        )
        mock_verify.return_value = mock_api_key
        mock_rate_limit.return_value = True

        mock_repo = AsyncMock()
        mock_repo.list_undelivered = AsyncMock(return_value=([], None))
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Test limit = 1 (minimum)
            response = await client.get(
                "/events/inbox?limit=1",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )
            assert response.status_code == status.HTTP_200_OK

            # Test limit = 200 (maximum)
            response = await client.get(
                "/events/inbox?limit=200",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )
            assert response.status_code == status.HTTP_200_OK

            # Test limit = 0 (invalid, below minimum)
            response = await client.get(
                "/events/inbox?limit=0",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST

            # Test limit = 201 (invalid, above maximum)
            response = await client.get(
                "/events/inbox?limit=201",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_get_inbox_invalid_cursor(valid_api_key, mock_api_key_model):
    """Test inbox with invalid cursor (should start from beginning)."""
    with patch(
        "src.auth.dependencies.verify_key_against_all"
    ) as mock_verify, patch(
        "src.services.event_service.EventRepository"
    ) as mock_repo_class, patch(
        "src.middleware.rate_limit.rate_limiter.check_rate_limit"
    ) as mock_rate_limit:
        # Setup mocks
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = True

        mock_repo = AsyncMock()
        mock_repo.list_undelivered = AsyncMock(return_value=([], None))
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/events/inbox?cursor=invalid_cursor_data",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        # Should succeed but start from beginning
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "events" in data
