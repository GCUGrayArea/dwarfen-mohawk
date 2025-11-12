"""Event service layer with business logic for event operations."""

import uuid
from datetime import datetime

from src.config import settings
from src.models.event import Event
from src.repositories.event_repository import EventRepository
from src.schemas.event import (
    CreateEventRequest,
    EventResponse,
    InboxEventItem,
    InboxResponse,
    PaginationMetadata,
)
from src.utils.deduplication import DeduplicationCache


class EventService:
    """
    Service layer for event operations.

    Orchestrates event ingestion, retrieval, and delivery acknowledgment.
    Implements deduplication logic and validates business rules.
    """

    def __init__(
        self,
        repository: EventRepository | None = None,
        dedup_cache: DeduplicationCache | None = None,
    ) -> None:
        """
        Initialize EventService.

        Args:
            repository: EventRepository instance (creates new if None)
            dedup_cache: DeduplicationCache instance (creates new if None)
        """
        self.repository = repository or EventRepository()
        self.dedup_cache = dedup_cache or DeduplicationCache(
            window_seconds=settings.deduplication_window_seconds
        )

    async def ingest(self, request: CreateEventRequest) -> EventResponse:
        """
        Ingest a new event.

        Generates event ID and timestamp, checks for duplicates,
        and persists event to DynamoDB.

        Args:
            request: CreateEventRequest with event data

        Returns:
            EventResponse with event ID and status
        """
        # Generate event ID and timestamp
        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Check for duplicates
        existing_id = self.dedup_cache.check_and_add(
            request.event_type, request.payload, event_id
        )

        if existing_id:
            # Duplicate detected, return existing event ID
            return EventResponse(
                status="accepted",
                event_id=existing_id,
                timestamp=timestamp,
                message="Event successfully ingested (duplicate detected)",
            )

        # Create event model
        event = Event(
            event_id=event_id,
            timestamp=timestamp,
            event_type=request.event_type,
            payload=request.payload,
            source=request.source,
            metadata=request.metadata,
            delivered=False,
            created_at=timestamp,
            updated_at=timestamp,
        )

        # Persist to DynamoDB
        await self.repository.create(event)

        return EventResponse(
            status="accepted",
            event_id=event_id,
            timestamp=timestamp,
            message="Event successfully ingested",
            event_type=event.event_type,
            payload=event.payload,
            source=event.source,
            delivered=event.delivered,
        )

    async def get(self, event_id: str, timestamp: str) -> EventResponse | None:
        """
        Get a specific event by ID and timestamp.

        Args:
            event_id: Event UUID
            timestamp: Event ISO 8601 timestamp

        Returns:
            EventResponse with event details, None if not found
        """
        event = await self.repository.get_by_id(event_id, timestamp)

        if not event:
            return None

        return EventResponse(
            status="success",
            event_id=event.event_id,
            timestamp=event.timestamp,
            message="Event retrieved successfully",
            event_type=event.event_type,
            payload=event.payload,
            source=event.source,
            delivered=event.delivered,
        )

    async def list_inbox(
        self, limit: int = 50, cursor: str | None = None
    ) -> InboxResponse:
        """
        List undelivered events with pagination.

        Args:
            limit: Maximum events to return (default 50, max 200)
            cursor: Opaque pagination cursor (None for first page)

        Returns:
            InboxResponse with events and pagination metadata
        """
        # Validate and clamp limit
        limit = min(max(1, limit), settings.max_inbox_limit)

        # Decode cursor (simplified - in production use base64)
        last_evaluated_key = None
        if cursor:
            # For MVP, cursor is just the last_evaluated_key dict
            # In production, would base64 encode/decode
            try:
                import json

                last_evaluated_key = json.loads(cursor)
            except Exception:
                # Invalid cursor, start from beginning
                last_evaluated_key = None

        # Query undelivered events
        events, next_key = await self.repository.list_undelivered(
            limit=limit, last_evaluated_key=last_evaluated_key
        )

        # Convert to response format
        event_items = [
            InboxEventItem(
                event_id=event.event_id,
                event_type=event.event_type,
                payload=event.payload,
                timestamp=event.timestamp,
                source=event.source,
            )
            for event in events
        ]

        # Encode next cursor
        next_cursor = None
        if next_key:
            import json

            next_cursor = json.dumps(next_key)

        # Get total count (simplified - just check if more results)
        # In production, might query GSI for count or cache this value
        total_undelivered = len(events)
        if next_key:
            # There are more results, so at least this many
            total_undelivered = limit + 1

        pagination = PaginationMetadata(
            next_cursor=next_cursor,
            has_more=next_key is not None,
            total_undelivered=total_undelivered,
        )

        return InboxResponse(events=event_items, pagination=pagination)

    async def mark_delivered(self, event_id: str, timestamp: str) -> bool:
        """
        Mark an event as delivered.

        Args:
            event_id: Event UUID
            timestamp: Event ISO 8601 timestamp

        Returns:
            True if successful, False if event not found
        """
        result = await self.repository.mark_delivered(event_id, timestamp)
        return result is not None
