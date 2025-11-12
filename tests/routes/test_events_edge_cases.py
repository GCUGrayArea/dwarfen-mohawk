"""Edge case tests for event API routes."""

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


@pytest.mark.asyncio
async def test_post_event_with_single_char_event_type(
    valid_api_key, mock_api_key_model
):
    """Test POST /events with single character event_type (minimum valid)."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch("src.services.event_service.EventRepository") as mock_repo_class,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)
        mock_repo_class.return_value = mock_repo

        request_data = {"event_type": "a", "payload": {"test": "data"}}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "accepted"


@pytest.mark.asyncio
async def test_post_event_with_max_length_event_type(valid_api_key, mock_api_key_model):
    """Test POST /events with 255 character event_type (maximum valid)."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch("src.services.event_service.EventRepository") as mock_repo_class,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)
        mock_repo_class.return_value = mock_repo

        request_data = {"event_type": "a" * 255, "payload": {"test": "data"}}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_post_event_with_empty_event_type(valid_api_key, mock_api_key_model):
    """Test POST /events with empty event_type returns validation error."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        request_data = {"event_type": "", "payload": {"test": "data"}}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_post_event_with_too_long_event_type(valid_api_key, mock_api_key_model):
    """Test POST /events with 256+ char event_type returns validation error."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        request_data = {"event_type": "a" * 256, "payload": {"test": "data"}}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_post_event_with_empty_payload(valid_api_key, mock_api_key_model):
    """Test POST /events with empty payload dictionary."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch("src.services.event_service.EventRepository") as mock_repo_class,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)
        mock_repo_class.return_value = mock_repo

        request_data = {"event_type": "test.empty", "payload": {}}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_post_event_with_very_large_payload(valid_api_key, mock_api_key_model):
    """Test POST /events with payload exceeding 256KB."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        # Create payload larger than 256KB
        target_size = 257 * 1024
        overhead = len('{"data":""}')
        value_size = target_size - overhead

        large_payload = {"data": "x" * value_size}
        request_data = {"event_type": "test.large", "payload": large_payload}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_post_event_with_complex_nested_payload(
    valid_api_key, mock_api_key_model
):
    """Test POST /events with deeply nested payload structure."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch("src.services.event_service.EventRepository") as mock_repo_class,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)
        mock_repo_class.return_value = mock_repo

        complex_payload = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "data": "nested",
                            "array": [1, 2, 3, {"key": "value"}],
                        }
                    }
                }
            },
            "array": [1, 2, 3, [4, 5, [6, 7]]],
        }

        request_data = {"event_type": "test.nested", "payload": complex_payload}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_get_inbox_with_limit_one(valid_api_key, mock_api_key_model):
    """Test GET /inbox with limit=1 (minimum valid value)."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch("src.services.event_service.EventRepository") as mock_repo_class,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        mock_repo = AsyncMock()
        mock_repo.list_undelivered = AsyncMock(return_value=([], None))
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/events/inbox?limit=1",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_get_inbox_with_limit_200(valid_api_key, mock_api_key_model):
    """Test GET /inbox with limit=200 (maximum valid value)."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch("src.services.event_service.EventRepository") as mock_repo_class,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        mock_repo = AsyncMock()
        mock_repo.list_undelivered = AsyncMock(return_value=([], None))
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/events/inbox?limit=200",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_get_inbox_with_invalid_cursor(valid_api_key, mock_api_key_model):
    """Test GET /inbox with malformed cursor."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch("src.services.event_service.EventRepository") as mock_repo_class,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        mock_repo = AsyncMock()
        mock_repo.list_undelivered = AsyncMock(return_value=([], None))
        mock_repo_class.return_value = mock_repo

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/events/inbox?cursor=invalid-cursor-data",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        # Should handle gracefully (fall back to beginning)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_get_inbox_with_cursor_special_chars(valid_api_key, mock_api_key_model):
    """Test GET /inbox with cursor containing special characters."""
    import json

    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch("src.services.event_service.EventRepository") as mock_repo_class,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        mock_repo = AsyncMock()
        mock_repo.list_undelivered = AsyncMock(return_value=([], None))
        mock_repo_class.return_value = mock_repo

        cursor_data = {
            "event_id": "test-!@#$%",
            "timestamp": "2025-11-11T12:00:00Z",
        }
        cursor = json.dumps(cursor_data)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/events/inbox?cursor={cursor}",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_get_inbox_with_negative_limit_returns_400(
    valid_api_key, mock_api_key_model
):
    """Test GET /inbox with negative limit returns validation error."""
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
            response = await client.get(
                "/events/inbox?limit=-10",
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        # FastAPI validates query parameters and returns 400 for invalid values
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_post_event_missing_payload_field(valid_api_key, mock_api_key_model):
    """Test POST /events missing required payload field."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        # Missing payload field entirely
        request_data = {"event_type": "test.event"}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_post_event_missing_event_type_field(valid_api_key, mock_api_key_model):
    """Test POST /events missing required event_type field."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        # Missing event_type field entirely
        request_data = {"payload": {"test": "data"}}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_post_event_with_null_payload(valid_api_key, mock_api_key_model):
    """Test POST /events with null payload."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        request_data = {"event_type": "test.event", "payload": None}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_post_event_with_array_payload(valid_api_key, mock_api_key_model):
    """Test POST /events with array instead of object for payload."""
    with (
        patch("src.auth.dependencies.verify_key_against_all") as mock_verify,
        patch(
            "src.middleware.rate_limit.rate_limiter.check_rate_limit"
        ) as mock_rate_limit,
    ):
        mock_verify.return_value = mock_api_key_model
        mock_rate_limit.return_value = None

        request_data = {"event_type": "test.event", "payload": [1, 2, 3]}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/events",
                json=request_data,
                headers={"Authorization": f"Bearer {valid_api_key}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
