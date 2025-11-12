"""Integration tests for full event lifecycle."""

import pytest
from fastapi import status
from httpx import AsyncClient

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_full_event_lifecycle(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    dynamodb_tables
):
    """
    Test complete event lifecycle: POST → GET inbox → GET event → DELETE → verify.

    This test verifies that:
    1. Event can be created via POST /events
    2. Event appears in inbox via GET /inbox
    3. Event can be retrieved by ID via GET /events/{event_id}
    4. Event can be marked as delivered via DELETE /events/{event_id}
    5. Event no longer appears in inbox after deletion
    """
    # Step 1: Create an event
    event_data = {
        "event_type": "user.signup",
        "payload": {
            "user_id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User"
        },
        "source": "integration-test",
        "metadata": {"test": "lifecycle"}
    }

    create_response = await api_client.post(
        "/events",
        json=event_data,
        headers=auth_headers
    )

    assert create_response.status_code == status.HTTP_200_OK
    create_data = create_response.json()
    assert create_data["status"] == "accepted"
    assert "event_id" in create_data
    assert "timestamp" in create_data

    event_id = create_data["event_id"]
    timestamp = create_data["timestamp"]

    # Step 2: Verify event appears in inbox
    inbox_response = await api_client.get(
        "/inbox",
        headers=auth_headers
    )

    assert inbox_response.status_code == status.HTTP_200_OK
    inbox_data = inbox_response.json()
    assert "events" in inbox_data
    assert len(inbox_data["events"]) == 1

    inbox_event = inbox_data["events"][0]
    assert inbox_event["event_id"] == event_id
    assert inbox_event["event_type"] == "user.signup"
    assert inbox_event["payload"]["user_id"] == "test-user-123"

    # Step 3: Retrieve specific event by ID
    get_response = await api_client.get(
        f"/events/{event_id}",
        params={"timestamp": timestamp},
        headers=auth_headers
    )

    assert get_response.status_code == status.HTTP_200_OK
    event_detail = get_response.json()
    assert event_detail["event_id"] == event_id
    assert event_detail["event_type"] == "user.signup"
    assert event_detail["payload"]["email"] == "test@example.com"
    assert event_detail["delivered"] is False

    # Step 4: Mark event as delivered (DELETE)
    delete_response = await api_client.delete(
        f"/events/{event_id}",
        params={"timestamp": timestamp},
        headers=auth_headers
    )

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Step 5: Verify event no longer appears in inbox
    inbox_after_delete = await api_client.get(
        "/inbox",
        headers=auth_headers
    )

    assert inbox_after_delete.status_code == status.HTTP_200_OK
    inbox_after_data = inbox_after_delete.json()
    assert len(inbox_after_data["events"]) == 0

    # Step 6: Verify event still exists but marked as delivered
    get_after_delete = await api_client.get(
        f"/events/{event_id}",
        params={"timestamp": timestamp},
        headers=auth_headers
    )

    assert get_after_delete.status_code == status.HTTP_200_OK
    delivered_event = get_after_delete.json()
    assert delivered_event["delivered"] is True


@pytest.mark.asyncio
async def test_pagination_with_multiple_events(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    dynamodb_tables
):
    """
    Test pagination with multiple events in inbox.

    Creates 10 events and verifies pagination works correctly.
    """
    # Create 10 events
    event_ids = []
    for i in range(10):
        event_data = {
            "event_type": f"test.event.{i}",
            "payload": {"index": i, "test": "pagination"},
            "source": "integration-test"
        }

        response = await api_client.post(
            "/events",
            json=event_data,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        event_ids.append(response.json()["event_id"])

    # Fetch first page (limit=5)
    page1_response = await api_client.get(
        "/inbox",
        params={"limit": 5},
        headers=auth_headers
    )

    assert page1_response.status_code == status.HTTP_200_OK
    page1_data = page1_response.json()
    assert len(page1_data["events"]) == 5
    assert page1_data["pagination"]["has_more"] is True
    assert page1_data["pagination"]["next_cursor"] is not None

    # Fetch second page using cursor
    cursor = page1_data["pagination"]["next_cursor"]
    page2_response = await api_client.get(
        "/inbox",
        params={"limit": 5, "cursor": cursor},
        headers=auth_headers
    )

    assert page2_response.status_code == status.HTTP_200_OK
    page2_data = page2_response.json()
    assert len(page2_data["events"]) == 5
    assert page2_data["pagination"]["has_more"] is False
    assert page2_data["pagination"]["next_cursor"] is None

    # Verify no duplicate events between pages
    page1_ids = {e["event_id"] for e in page1_data["events"]}
    page2_ids = {e["event_id"] for e in page2_data["events"]}
    assert len(page1_ids.intersection(page2_ids)) == 0

    # Verify all events are present across both pages
    all_fetched_ids = page1_ids.union(page2_ids)
    assert all_fetched_ids == set(event_ids)


@pytest.mark.asyncio
async def test_empty_inbox(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    dynamodb_tables
):
    """Test that empty inbox returns empty array."""
    response = await api_client.get(
        "/inbox",
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["events"] == []
    assert data["pagination"]["has_more"] is False
    assert data["pagination"]["next_cursor"] is None


@pytest.mark.asyncio
async def test_delete_idempotency(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    dynamodb_tables
):
    """Test that DELETE is idempotent (returns 204 for already-delivered)."""
    # Create event
    event_data = {
        "event_type": "test.delete.idempotent",
        "payload": {"test": "idempotency"}
    }

    create_response = await api_client.post(
        "/events",
        json=event_data,
        headers=auth_headers
    )

    event_id = create_response.json()["event_id"]
    timestamp = create_response.json()["timestamp"]

    # Delete first time
    delete1 = await api_client.delete(
        f"/events/{event_id}",
        params={"timestamp": timestamp},
        headers=auth_headers
    )
    assert delete1.status_code == status.HTTP_204_NO_CONTENT

    # Delete second time (should still return 204)
    delete2 = await api_client.delete(
        f"/events/{event_id}",
        params={"timestamp": timestamp},
        headers=auth_headers
    )
    assert delete2.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_get_nonexistent_event(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    dynamodb_tables
):
    """Test that GET returns 404 for non-existent event."""
    response = await api_client.get(
        "/events/nonexistent-id-12345",
        params={"timestamp": "2025-11-11T00:00:00Z"},
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "EVENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_nonexistent_event(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    dynamodb_tables
):
    """Test that DELETE returns 404 for non-existent event."""
    response = await api_client.delete(
        "/events/nonexistent-id-12345",
        params={"timestamp": "2025-11-11T00:00:00Z"},
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "EVENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_pagination_with_max_limit(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    dynamodb_tables
):
    """Test that pagination respects maximum limit of 200."""
    response = await api_client.get(
        "/inbox",
        params={"limit": 250},  # Request more than max
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["status"] == "error"
    assert "limit" in data["message"].lower()


@pytest.mark.asyncio
async def test_pagination_with_invalid_cursor(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    dynamodb_tables
):
    """Test that invalid cursor returns 400 error."""
    response = await api_client.get(
        "/inbox",
        params={"cursor": "invalid_cursor_string"},
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["status"] == "error"
    assert "cursor" in data["message"].lower()
