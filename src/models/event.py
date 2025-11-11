"""Event model for DynamoDB."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    """
    Event model representing an ingested event in the Triggers API.

    Attributes:
        event_id: Unique identifier (UUID v4)
        timestamp: ISO 8601 timestamp of event creation
        event_type: Type/category of event (max 255 chars)
        payload: Arbitrary JSON data (max 256KB)
        source: Optional source identifier
        metadata: Optional additional metadata
        delivered: Whether event has been consumed/delivered
        created_at: ISO 8601 timestamp of record creation
        updated_at: ISO 8601 timestamp of last update
        ttl: Unix timestamp for DynamoDB TTL (optional)
    """

    event_id: str = Field(..., description="Unique event identifier (UUID)")
    timestamp: str = Field(..., description="ISO 8601 event timestamp")
    event_type: str = Field(
        ..., min_length=1, max_length=255, description="Event type"
    )
    payload: Dict[str, Any] = Field(..., description="Event payload (JSON)")
    source: Optional[str] = Field(None, description="Event source")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata"
    )
    delivered: bool = Field(
        default=False, description="Delivery status"
    )
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    updated_at: str = Field(..., description="ISO 8601 update timestamp")
    ttl: Optional[int] = Field(
        None, description="Unix timestamp for TTL"
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-11-11T12:00:00Z",
                "event_type": "user.signup",
                "payload": {"user_id": "123", "email": "user@example.com"},
                "source": "web-app",
                "metadata": {"ip": "192.168.1.1"},
                "delivered": False,
                "created_at": "2025-11-11T12:00:00Z",
                "updated_at": "2025-11-11T12:00:00Z",
            }
        }
