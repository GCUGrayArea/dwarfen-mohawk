"""Tests for GET /status endpoint."""

import time
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_status_endpoint_returns_200() -> None:
    """Test that status endpoint returns 200 OK."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/status")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_status_endpoint_returns_json() -> None:
    """Test that status endpoint returns JSON."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/status")

    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_status_endpoint_has_required_fields() -> None:
    """Test that status endpoint response has required fields."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/status")

    data: dict[str, Any] = response.json()

    # Required fields
    assert "status" in data
    assert "version" in data
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_status_field_is_ok() -> None:
    """Test that status field is 'ok'."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/status")

    data: dict[str, Any] = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_version_field_is_string() -> None:
    """Test that version field is a non-empty string."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/status")

    data: dict[str, Any] = response.json()
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0


@pytest.mark.asyncio
async def test_uptime_is_integer() -> None:
    """Test that uptime_seconds is an integer."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/status")

    data: dict[str, Any] = response.json()
    assert isinstance(data["uptime_seconds"], int)


@pytest.mark.asyncio
async def test_uptime_is_non_negative() -> None:
    """Test that uptime_seconds is non-negative."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/status")

    data: dict[str, Any] = response.json()
    assert data["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_uptime_increases_over_time() -> None:
    """Test that uptime_seconds increases on subsequent calls."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response1 = await client.get("/status")
        data1: dict[str, Any] = response1.json()
        uptime1: int = data1["uptime_seconds"]

        # Wait a moment
        time.sleep(1.1)

        response2 = await client.get("/status")
        data2: dict[str, Any] = response2.json()
        uptime2: int = data2["uptime_seconds"]

    # Uptime should increase by at least 1 second
    assert uptime2 >= uptime1 + 1


@pytest.mark.asyncio
async def test_status_endpoint_no_authentication_required() -> None:
    """Test that status endpoint does not require authentication."""
    # Request without Authorization header should succeed
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/status")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_status_endpoint_response_time() -> None:
    """Test that status endpoint responds quickly (< 100ms)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        start_time = time.time()
        response = await client.get("/status")
        end_time = time.time()

    response_time_ms = (end_time - start_time) * 1000

    # Should be fast (< 100ms, target is < 10ms but testing can be slower)
    assert response_time_ms < 100
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_status_endpoint_multiple_calls() -> None:
    """Test that status endpoint can be called multiple times."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for _ in range(5):
            response = await client.get("/status")
            assert response.status_code == 200
            data: dict[str, Any] = response.json()
            assert data["status"] == "ok"
