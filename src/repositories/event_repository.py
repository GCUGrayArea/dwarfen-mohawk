"""Event repository for DynamoDB operations."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aioboto3

from src.config import settings
from src.models.event import Event
from src.repositories.base import BaseRepository


class EventRepository(BaseRepository):
    """
    Repository for Event operations in DynamoDB.

    Provides async methods for creating, retrieving, updating,
    and deleting events.
    """

    def __init__(self) -> None:
        """Initialize EventRepository with events table."""
        super().__init__(settings.dynamodb_table_events)

    async def create(self, event: Event) -> Event:
        """
        Create a new event in DynamoDB.

        Args:
            event: Event model to store

        Returns:
            The created Event
        """
        item = event.model_dump()
        await self.put_item(item)
        return event

    async def get_by_id(
        self, event_id: str, timestamp: str
    ) -> Optional[Event]:
        """
        Get event by ID and timestamp.

        Args:
            event_id: Event partition key (UUID)
            timestamp: Event sort key (ISO 8601)

        Returns:
            Event if found, None otherwise
        """
        key = {"event_id": event_id, "timestamp": timestamp}
        item = await self.get_item(key)

        if item:
            return Event(**item)
        return None

    async def list_undelivered(
        self, limit: int = 50, last_evaluated_key: Optional[Dict] = None
    ) -> tuple[List[Event], Optional[Dict]]:
        """
        List undelivered events using GSI.

        Args:
            limit: Maximum number of events to return
            last_evaluated_key: For pagination (cursor)

        Returns:
            Tuple of (list of events, next cursor or None)
        """
        async with self.session.resource(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        ) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            query_params = {
                "IndexName": "DeliveredIndex",
                "KeyConditionExpression": "delivered = :delivered",
                "ExpressionAttributeValues": {":delivered": False},
                "Limit": limit,
                "ScanIndexForward": True,  # Chronological order
            }

            if last_evaluated_key:
                query_params["ExclusiveStartKey"] = last_evaluated_key

            response = await table.query(**query_params)

            events = [Event(**item) for item in response.get("Items", [])]
            next_key = response.get("LastEvaluatedKey")

            return events, next_key

    async def mark_delivered(
        self, event_id: str, timestamp: str
    ) -> Optional[Event]:
        """
        Mark event as delivered.

        Args:
            event_id: Event partition key (UUID)
            timestamp: Event sort key (ISO 8601)

        Returns:
            Updated Event if successful, None if not found
        """
        # Calculate TTL (30 days from now by default)
        ttl_days = settings.event_ttl_days
        ttl_timestamp = int(
            (datetime.utcnow() + timedelta(days=ttl_days)).timestamp()
        )

        key = {"event_id": event_id, "timestamp": timestamp}
        update_expr = (
            "SET delivered = :delivered, "
            "updated_at = :updated_at, "
            "ttl = :ttl"
        )
        expr_values = {
            ":delivered": True,
            ":updated_at": datetime.utcnow().isoformat() + "Z",
            ":ttl": ttl_timestamp,
        }

        try:
            result = await self.update_item(
                key, update_expr, expr_values
            )
            return Event(**result)
        except Exception:
            return None
