"""API Key model for DynamoDB."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ApiKey(BaseModel):
    """
    API Key model for authentication.

    Attributes:
        key_id: Unique identifier (UUID v4)
        key_hash: Bcrypt hash of the API key
        status: Key status (active, inactive, revoked)
        rate_limit: Requests per minute limit
        allowed_event_types: Optional list of allowed event types
        created_at: ISO 8601 timestamp of key creation
        last_used_at: ISO 8601 timestamp of last use
        description: Optional human-readable description
    """

    key_id: str = Field(..., description="Unique key identifier (UUID)")
    key_hash: str = Field(..., description="Bcrypt hash of API key")
    status: str = Field(
        ..., description="Key status: active, inactive, revoked"
    )
    rate_limit: int = Field(
        default=100, description="Requests per minute"
    )
    allowed_event_types: Optional[List[str]] = Field(
        None, description="List of allowed event types (None = all)"
    )
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    last_used_at: Optional[str] = Field(
        None, description="ISO 8601 last used timestamp"
    )
    description: Optional[str] = Field(
        None, description="Human-readable description"
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "key_id": "660e9500-f39c-52e5-b827-557766551111",
                "key_hash": "$2b$12$...",  # Bcrypt hash
                "status": "active",
                "rate_limit": 100,
                "allowed_event_types": None,
                "created_at": "2025-11-11T12:00:00Z",
                "last_used_at": None,
                "description": "Production API key",
            }
        }
