"""
Performance load testing scenarios for Zapier Triggers API.

This file defines Locust load test scenarios to measure API performance under
various load conditions. Run with: locust -f tests/performance/locustfile.py

Target metrics from PRD:
- POST /events p95 latency: < 100ms
- GET /inbox p95 latency: < 200ms
- Throughput: 1000+ events/second
"""

import random
import uuid
from typing import Any

from locust import HttpUser, between, task


class TriggersAPIUser(HttpUser):
    """
    Simulates a typical API user sending events, polling inbox, and
    acknowledging events.
    """

    # Wait 0.1-2 seconds between tasks (simulates realistic user behavior)
    wait_time = between(0.1, 2)

    def on_start(self) -> None:
        """
        Called when a simulated user starts. Sets up authentication.
        Override API_KEY via environment variable or --host parameter.
        """
        # Default test API key (should be configured for load testing)
        # In production, use environment variable: export LOCUST_API_KEY=...
        import os

        self.api_key = os.getenv("LOCUST_API_KEY", "test-api-key-change-me")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.created_event_ids: list[str] = []

    def generate_random_payload(self) -> dict[str, Any]:
        """Generate a random event payload for testing."""
        return {
            "user_id": f"user_{random.randint(1000, 9999)}",
            "action": random.choice(["click", "view", "submit", "delete"]),
            "resource": random.choice(["button", "form", "page", "item"]),
            "timestamp": "2025-11-11T12:00:00Z",
            "metadata": {
                "session_id": str(uuid.uuid4()),
                "ip_address": f"192.168.{random.randint(1,255)}.{random.randint(1,255)}",  # noqa: E501
                "user_agent": "Mozilla/5.0 (Test)",
            },
        }

    @task(10)
    def send_event(self) -> None:
        """
        Send a new event to the API.
        Weight: 10 (most common operation in typical usage).
        """
        event_data = {
            "event_type": f"test.{random.choice(['user', 'system', 'analytics'])}",  # noqa: E501
            "payload": self.generate_random_payload(),
            "source": "locust-load-test",
        }

        with self.client.post(
            "/events", json=event_data, headers=self.headers, catch_response=True
        ) as response:
            if response.status_code == 201:
                data = response.json()
                self.created_event_ids.append(data["event_id"])
                response.success()
            elif response.status_code == 429:
                # Rate limit hit - expected under load
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def poll_inbox(self) -> None:
        """
        Poll the inbox for undelivered events.
        Weight: 3 (less frequent than sending events).
        """
        params = {"limit": random.choice([10, 50, 100])}

        with self.client.get(
            "/inbox", params=params, headers=self.headers, catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def get_event_by_id(self) -> None:
        """
        Retrieve a specific event by ID.
        Weight: 2 (occasional lookups).
        """
        if not self.created_event_ids:
            # Skip if no events created yet
            return

        event_id = random.choice(self.created_event_ids)

        with self.client.get(
            f"/events/{event_id}", headers=self.headers, catch_response=True
        ) as response:
            if response.status_code in (200, 404):
                # 404 is acceptable (event may have been delivered/deleted)
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def acknowledge_event(self) -> None:
        """
        Acknowledge (delete) an event.
        Weight: 1 (least frequent operation).
        """
        if not self.created_event_ids:
            # Skip if no events created yet
            return

        event_id = self.created_event_ids.pop(0)

        with self.client.delete(
            f"/events/{event_id}", headers=self.headers, catch_response=True
        ) as response:
            if response.status_code in (204, 404):
                # Both success and not-found are acceptable
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def check_health(self) -> None:
        """
        Check API health endpoint.
        Weight: 1 (occasional health checks).
        """
        with self.client.get("/status", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class HighThroughputUser(HttpUser):
    """
    Simulates high-throughput event ingestion scenario.
    Used for stress testing event ingestion limits.
    """

    wait_time = between(0.01, 0.1)  # Very short wait time

    def on_start(self) -> None:
        """Setup authentication for high throughput testing."""
        import os

        self.api_key = os.getenv("LOCUST_API_KEY", "test-api-key-change-me")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @task
    def send_event_fast(self) -> None:
        """Send events as fast as possible to test throughput limits."""
        event_data = {
            "event_type": "stress.test",
            "payload": {
                "id": str(uuid.uuid4()),
                "value": random.randint(1, 1000),
            },
        }

        with self.client.post(
            "/events", json=event_data, headers=self.headers, catch_response=True
        ) as response:
            if response.status_code in (201, 429):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
