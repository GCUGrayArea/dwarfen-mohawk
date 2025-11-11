"""Tests for GET /events/{event_id} endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from src.auth.dependencies import require_api_key
from src.main import app
from src.models.api_key import ApiKey
from src.schemas.event import EventResponse


@pytest.fixture
def mock_api_key():
    """Mock API key for authentication."""
    return ApiKey(
        key_id="test-key-123",
        key_hash="$2b$12$test_hash",
        status="active",
        rate_limit=100,
        created_at="2025-11-11T00:00:00Z",
        last_used_at="2025-11-11T00:00:00Z",
    )


@pytest.fixture
def mock_event_response():
    """Mock event response."""
    return EventResponse(
        status="success",
        event_id="550e8400-e29b-41d4-a716-446655440000",
        timestamp="2025-11-11T12:00:00Z",
        message="Event retrieved successfully",
        event_type="user.signup",
        payload={"user_id": "123", "email": "test@example.com"},
        source="web-app",
        delivered=False,
    )


@pytest.mark.asyncio
async def test_get_event_success(mock_api_key, mock_event_response):
    """Test successful event retrieval."""
    async def override_require_api_key():
        return mock_api_key

    mock_service = MagicMock()
    mock_service.get = AsyncMock(return_value=mock_event_response)

    app.dependency_overrides[require_api_key] = override_require_api_key

    with patch("src.routes.events.EventService", return_value=mock_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/events/550e8400-e29b-41d4-a716-446655440000",
                params={"timestamp": "2025-11-11T12:00:00Z"},
                headers={"Authorization": "Bearer test-key"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert data["event_type"] == "user.signup"
    assert data["payload"]["user_id"] == "123"
    assert data["delivered"] is False


@pytest.mark.asyncio
async def test_get_event_not_found(mock_api_key):
    """Test event not found returns 404."""
    async def override_require_api_key():
        return mock_api_key

    mock_service = MagicMock()
    mock_service.get = AsyncMock(return_value=None)

    app.dependency_overrides[require_api_key] = override_require_api_key

    with patch("src.routes.events.EventService", return_value=mock_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/events/nonexistent-id",
                params={"timestamp": "2025-11-11T12:00:00Z"},
                headers={"Authorization": "Bearer test-key"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "NOT_FOUND"
    assert "nonexistent-id" in data["message"]


@pytest.mark.asyncio
async def test_get_event_unauthorized():
    """Test GET without API key returns 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get(
            "/events/550e8400-e29b-41d4-a716-446655440000",
            params={"timestamp": "2025-11-11T12:00:00Z"},
        )

    assert response.status_code == 401
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_get_event_missing_timestamp(mock_api_key):
    """Test GET without timestamp parameter returns 400."""
    async def override_require_api_key():
        return mock_api_key

    app.dependency_overrides[require_api_key] = override_require_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get(
            "/events/550e8400-e29b-41d4-a716-446655440000",
            headers={"Authorization": "Bearer test-key"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_event_delivered(mock_api_key):
    """Test retrieving a delivered event."""
    delivered_event = EventResponse(
        status="success",
        event_id="550e8400-e29b-41d4-a716-446655440000",
        timestamp="2025-11-11T12:00:00Z",
        message="Event retrieved successfully",
        event_type="user.signup",
        payload={"user_id": "123"},
        source="web-app",
        delivered=True,
    )

    async def override_require_api_key():
        return mock_api_key

    mock_service = MagicMock()
    mock_service.get = AsyncMock(return_value=delivered_event)

    app.dependency_overrides[require_api_key] = override_require_api_key

    with patch("src.routes.events.EventService", return_value=mock_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/events/550e8400-e29b-41d4-a716-446655440000",
                params={"timestamp": "2025-11-11T12:00:00Z"},
                headers={"Authorization": "Bearer test-key"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["delivered"] is True
