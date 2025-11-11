"""Pydantic schemas for event API requests and responses."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class CreateEventRequest(BaseModel):
    """
    Request schema for creating a new event.

    Attributes:
        event_type: Type/category of event (required, max 255 chars)
        payload: Arbitrary JSON data (required, max 256KB)
        source: Optional source identifier
        metadata: Optional additional metadata
    """

    event_type: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Event type (required, 1-255 chars)",
    )
    payload: Dict[str, Any] = Field(
        ..., description="Event payload (JSON, max 256KB)"
    )
    source: Optional[str] = Field(None, description="Event source")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata"
    )

    @field_validator("payload")
    @classmethod
    def validate_payload_size(
        cls, v: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate payload size is under 256KB.

        Args:
            v: Payload dictionary

        Returns:
            Validated payload

        Raises:
            ValueError: If payload exceeds 256KB
        """
        import json

        payload_size = len(json.dumps(v).encode("utf-8"))
        max_size = 256 * 1024  # 256KB

        if payload_size > max_size:
            raise ValueError(
                f"Payload size ({payload_size} bytes) "
                f"exceeds maximum of {max_size} bytes"
            )

        return v

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "event_type": "user.signup",
                "payload": {"user_id": "123", "email": "user@example.com"},
                "source": "web-app",
                "metadata": {"ip": "192.168.1.1"},
            }
        }


class EventResponse(BaseModel):
    """
    Response schema for a single event.

    Attributes:
        status: Operation status ("accepted", "error")
        event_id: Unique event identifier (UUID)
        timestamp: ISO 8601 timestamp
        message: Human-readable message
        event_type: Event type (for full event details)
        payload: Event payload (for full event details)
        source: Event source (for full event details)
        delivered: Delivery status (for full event details)
    """

    status: str = Field(..., description="Operation status")
    event_id: str = Field(..., description="Event UUID")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    message: str = Field(..., description="Human-readable message")
    event_type: Optional[str] = Field(None, description="Event type")
    payload: Optional[Dict[str, Any]] = Field(None, description="Payload")
    source: Optional[str] = Field(None, description="Event source")
    delivered: Optional[bool] = Field(None, description="Delivered status")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "status": "accepted",
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-11-11T12:00:00Z",
                "message": "Event successfully ingested",
            }
        }


class InboxEventItem(BaseModel):
    """
    Individual event in inbox response.

    Attributes:
        event_id: Unique event identifier (UUID)
        event_type: Type/category of event
        payload: Event payload (JSON)
        timestamp: ISO 8601 timestamp
        source: Optional source identifier
    """

    event_id: str = Field(..., description="Event UUID")
    event_type: str = Field(..., description="Event type")
    payload: Dict[str, Any] = Field(..., description="Event payload")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    source: Optional[str] = Field(None, description="Event source")


class PaginationMetadata(BaseModel):
    """
    Pagination metadata for inbox response.

    Attributes:
        next_cursor: Opaque cursor token for next page (null if no more)
        has_more: Whether there are more events to retrieve
        total_undelivered: Total count of undelivered events
    """

    next_cursor: Optional[str] = Field(
        None, description="Next page cursor (null if last page)"
    )
    has_more: bool = Field(..., description="More events available")
    total_undelivered: int = Field(
        ..., description="Total undelivered event count"
    )


class InboxResponse(BaseModel):
    """
    Response schema for inbox endpoint (list of undelivered events).

    Attributes:
        events: List of undelivered events
        pagination: Pagination metadata
    """

    events: List[InboxEventItem] = Field(
        ..., description="List of undelivered events"
    )
    pagination: PaginationMetadata = Field(
        ..., description="Pagination metadata"
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "events": [
                    {
                        "event_id": "550e8400-e29b-41d4-a716-446655440000",
                        "event_type": "user.signup",
                        "payload": {
                            "user_id": "123",
                            "email": "user@example.com",
                        },
                        "timestamp": "2025-11-11T12:00:00Z",
                        "source": "web-app",
                    }
                ],
                "pagination": {
                    "next_cursor": "eyJsYXN0X2V2ZW50X2lkIjoi...",
                    "has_more": True,
                    "total_undelivered": 150,
                },
            }
        }
