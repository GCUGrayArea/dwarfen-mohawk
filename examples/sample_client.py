"""
Sample Python client for Zapier Triggers API.

Demonstrates common workflows:
- Sending events with authentication
- Polling inbox with pagination
- Acknowledging events after processing
- Error handling and retry logic

Requirements:
    pip install httpx python-dotenv
"""

import asyncio
import os
import sys
import time
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv


class TriggersAPIClient:
    """
    Async client for Zapier Triggers API.

    Handles authentication, rate limiting, retries, and common workflows.
    """

    def __init__(
        self, api_key: str, base_url: str = "http://localhost:8000"
    ) -> None:
        """
        Initialize the API client.

        Args:
            api_key: API key for authentication
            base_url: Base URL of the Triggers API
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> "TriggersAPIClient":
        """Context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Context manager exit."""
        await self.close()

    async def send_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Send an event to the API with automatic retry logic.

        Args:
            event_type: Event type (e.g., "user.signup")
            payload: Event payload data
            source: Optional source identifier
            metadata: Optional metadata
            max_retries: Maximum retry attempts for 5xx errors

        Returns:
            API response with event_id and timestamp

        Raises:
            httpx.HTTPStatusError: If request fails after retries
        """
        request_data: Dict[str, Any] = {
            "event_type": event_type,
            "payload": payload,
        }
        if source:
            request_data["source"] = source
        if metadata:
            request_data["metadata"] = metadata

        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    "/events", json=request_data
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited - respect Retry-After header
                    retry_after = int(
                        e.response.headers.get("Retry-After", "60")
                    )
                    print(
                        f"Rate limited. Waiting {retry_after}s...",
                        file=sys.stderr,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                elif e.response.status_code >= 500:
                    # Server error - retry with exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = 2**attempt
                        print(
                            f"Server error. Retry {attempt + 1}/"
                            f"{max_retries} in {wait_time}s...",
                            file=sys.stderr,
                        )
                        await asyncio.sleep(wait_time)
                        continue

                # Client error (4xx) or final attempt - raise
                print(
                    f"Error sending event: {e.response.status_code}",
                    file=sys.stderr,
                )
                print(f"Response: {e.response.text}", file=sys.stderr)
                raise

        raise Exception("Max retries exceeded")

    async def poll_inbox(
        self, limit: int = 50, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Poll the inbox for undelivered events.

        Args:
            limit: Maximum events to retrieve (1-200)
            cursor: Pagination cursor from previous response

        Returns:
            Response with events list and pagination metadata

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        params: Dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        response = await self.client.get("/events/inbox", params=params)
        response.raise_for_status()
        return response.json()

    async def acknowledge_event(
        self, event_id: str, timestamp: str
    ) -> None:
        """
        Acknowledge an event as delivered (soft delete).

        Args:
            event_id: Event UUID
            timestamp: Event ISO 8601 timestamp

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        params = {"timestamp": timestamp}
        response = await self.client.delete(
            f"/events/{event_id}", params=params
        )
        response.raise_for_status()

    async def get_event(
        self, event_id: str, timestamp: str
    ) -> Dict[str, Any]:
        """
        Retrieve a specific event by ID and timestamp.

        Args:
            event_id: Event UUID
            timestamp: Event ISO 8601 timestamp

        Returns:
            Full event details

        Raises:
            httpx.HTTPStatusError: If request fails (404 if not found)
        """
        params = {"timestamp": timestamp}
        response = await self.client.get(
            f"/events/{event_id}", params=params
        )
        response.raise_for_status()
        return response.json()


async def example_send_event(client: TriggersAPIClient) -> None:
    """Example: Send a single event."""
    print("\n=== Example 1: Send Event ===")

    response = await client.send_event(
        event_type="user.signup",
        payload={
            "user_id": "user_12345",
            "email": "alice@example.com",
            "plan": "pro",
        },
        source="web-app",
        metadata={"ip": "192.168.1.1"},
    )

    print(f"Event sent successfully!")
    print(f"  Event ID: {response['event_id']}")
    print(f"  Timestamp: {response['timestamp']}")
    print(f"  Status: {response['status']}")


async def example_poll_inbox(client: TriggersAPIClient) -> List[Dict]:
    """Example: Poll inbox with pagination."""
    print("\n=== Example 2: Poll Inbox ===")

    all_events: List[Dict] = []
    cursor: Optional[str] = None
    page = 1

    while True:
        response = await client.poll_inbox(limit=10, cursor=cursor)
        events = response["events"]
        pagination = response["pagination"]

        print(f"Page {page}: Retrieved {len(events)} events")
        all_events.extend(events)

        if not pagination["has_more"]:
            break

        cursor = pagination["next_cursor"]
        page += 1

    print(f"Total events in inbox: {len(all_events)}")
    return all_events


async def example_acknowledge_events(
    client: TriggersAPIClient, events: List[Dict]
) -> None:
    """Example: Acknowledge events after processing."""
    print("\n=== Example 3: Acknowledge Events ===")

    for event in events[:3]:  # Process first 3 events
        event_id = event["event_id"]
        timestamp = event["timestamp"]

        # Simulate processing
        print(f"Processing event {event_id}...")
        await asyncio.sleep(0.1)

        # Acknowledge as delivered
        await client.acknowledge_event(event_id, timestamp)
        print(f"  Acknowledged {event_id}")


async def example_error_handling(client: TriggersAPIClient) -> None:
    """Example: Error handling for common scenarios."""
    print("\n=== Example 4: Error Handling ===")

    # Invalid event (empty event_type)
    try:
        await client.send_event(event_type="", payload={})
    except httpx.HTTPStatusError as e:
        print(f"Validation error (expected): {e.response.status_code}")

    # Non-existent event
    try:
        await client.get_event(
            event_id="nonexistent-id", timestamp="2025-01-01T00:00:00Z"
        )
    except httpx.HTTPStatusError as e:
        print(f"Not found error (expected): {e.response.status_code}")


async def main() -> None:
    """
    Main example workflow demonstrating the API client.

    Demonstrates:
    1. Sending events
    2. Polling inbox
    3. Acknowledging events
    4. Error handling
    """
    # Load API key from environment
    load_dotenv()
    api_key = os.getenv("TRIGGERS_API_KEY")

    if not api_key:
        print(
            "Error: TRIGGERS_API_KEY not set in environment",
            file=sys.stderr,
        )
        print("Set it in .env file or export TRIGGERS_API_KEY=your_key")
        sys.exit(1)

    # Create client with context manager (auto-closes)
    async with TriggersAPIClient(api_key=api_key) as client:
        # Example 1: Send an event
        await example_send_event(client)

        # Example 2: Poll inbox with pagination
        events = await example_poll_inbox(client)

        # Example 3: Acknowledge events
        if events:
            await example_acknowledge_events(client, events)

        # Example 4: Error handling
        await example_error_handling(client)

    print("\n=== All examples completed ===")


if __name__ == "__main__":
    asyncio.run(main())
