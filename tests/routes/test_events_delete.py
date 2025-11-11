"""Tests for DELETE /events/{event_id} endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from src.auth.dependencies import require_api_key
from src.main import app
from src.models.api_key import ApiKey


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


@pytest.mark.asyncio
async def test_delete_event_success(mock_api_key):
    """Test successful event deletion."""
    async def override_require_api_key():
        return mock_api_key

    mock_service = MagicMock()
    mock_service.mark_delivered = AsyncMock(return_value=True)

    app.dependency_overrides[require_api_key] = override_require_api_key

    with patch("src.routes.events.EventService", return_value=mock_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.delete(
                "/events/550e8400-e29b-41d4-a716-446655440000",
                params={"timestamp": "2025-11-11T12:00:00Z"},
                headers={"Authorization": "Bearer test-key"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.asyncio
async def test_delete_event_not_found(mock_api_key):
    """Test deleting non-existent event returns 404."""
    async def override_require_api_key():
        return mock_api_key

    mock_service = MagicMock()
    mock_service.mark_delivered = AsyncMock(return_value=False)

    app.dependency_overrides[require_api_key] = override_require_api_key

    with patch("src.routes.events.EventService", return_value=mock_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.delete(
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
async def test_delete_event_idempotent(mock_api_key):
    """Test that DELETE is idempotent (already delivered returns 204)."""
    async def override_require_api_key():
        return mock_api_key

    mock_service = MagicMock()
    mock_service.mark_delivered = AsyncMock(return_value=True)

    app.dependency_overrides[require_api_key] = override_require_api_key

    with patch("src.routes.events.EventService", return_value=mock_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            # First delete
            response1 = await client.delete(
                "/events/550e8400-e29b-41d4-a716-446655440000",
                params={"timestamp": "2025-11-11T12:00:00Z"},
                headers={"Authorization": "Bearer test-key"},
            )

            # Second delete (idempotent)
            response2 = await client.delete(
                "/events/550e8400-e29b-41d4-a716-446655440000",
                params={"timestamp": "2025-11-11T12:00:00Z"},
                headers={"Authorization": "Bearer test-key"},
            )

    app.dependency_overrides.clear()

    assert response1.status_code == 204
    assert response2.status_code == 204
    assert mock_service.mark_delivered.call_count == 2


@pytest.mark.asyncio
async def test_delete_event_unauthorized():
    """Test DELETE without API key returns 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.delete(
            "/events/550e8400-e29b-41d4-a716-446655440000",
            params={"timestamp": "2025-11-11T12:00:00Z"},
        )

    assert response.status_code == 401
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_delete_event_missing_timestamp(mock_api_key):
    """Test DELETE without timestamp parameter returns 400."""
    async def override_require_api_key():
        return mock_api_key

    app.dependency_overrides[require_api_key] = override_require_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.delete(
            "/events/550e8400-e29b-41d4-a716-446655440000",
            headers={"Authorization": "Bearer test-key"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_event_service_error(mock_api_key):
    """Test DELETE handles service errors gracefully."""
    async def override_require_api_key():
        return mock_api_key

    mock_service = MagicMock()
    mock_service.mark_delivered = AsyncMock(
        side_effect=Exception("Database error")
    )

    app.dependency_overrides[require_api_key] = override_require_api_key

    with patch("src.routes.events.EventService", return_value=mock_service):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.delete(
                "/events/550e8400-e29b-41d4-a716-446655440000",
                params={"timestamp": "2025-11-11T12:00:00Z"},
                headers={"Authorization": "Bearer test-key"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 500
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "INTERNAL_ERROR"
