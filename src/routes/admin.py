"""Admin routes for demo and management operations.

WARNING: These endpoints are for DEMO purposes only.
In production, they should be protected or removed entirely.
"""

import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from src.auth.api_key import hash_api_key
from src.models.api_key import ApiKey
from src.repositories.api_key_repository import ApiKeyRepository

router = APIRouter(prefix="/admin", tags=["Admin"])


class GenerateKeyRequest(BaseModel):
    """Request to generate a new API key."""

    user_email: str = Field(
        default="demo@example.com", description="Email for the demo user"
    )
    role: str = Field(default="creator", description="Role (viewer or creator)")


class GenerateKeyResponse(BaseModel):
    """Response with generated API key details."""

    key_id: str = Field(..., description="Unique key identifier")
    api_key: str = Field(..., description="Plaintext API key (save this!)")
    user_email: str = Field(..., description="User email")
    role: str = Field(..., description="User role")
    status: str = Field(..., description="Key status")
    rate_limit: int = Field(..., description="Requests per minute limit")
    created_at: str = Field(..., description="Creation timestamp")
    warning: str = Field(
        ..., description="Security warning about this being demo-only"
    )


@router.post(
    "/generate-key",
    response_model=GenerateKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Demo API Key",
    description=(
        "Generate a new API key for demo purposes. "
        "WARNING: This endpoint is unauthenticated and should only be used "
        "in demo environments. Remove or protect this endpoint in production."
    ),
)
async def generate_demo_key(
    request: GenerateKeyRequest | None = None,
) -> GenerateKeyResponse:
    """
    Generate a new API key for demo purposes.

    This endpoint creates a new API key without authentication.
    It's designed for demo environments where users need to
    quickly get started without CLI access.

    Args:
        request: Optional parameters for key generation

    Returns:
        GenerateKeyResponse with the plaintext API key

    WARNING: This is a security risk in production. The API key
    is returned in plaintext and the endpoint has no authentication.
    """
    # Use defaults if no request body provided
    if request is None:
        request = GenerateKeyRequest()

    # Generate a secure random API key (64 characters)
    api_key_plaintext = secrets.token_urlsafe(48)[:64].ljust(64, "0")

    # Hash the key for storage
    key_hash = hash_api_key(api_key_plaintext)

    # Create the key record
    key_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    api_key_model = ApiKey(
        key_id=key_id,
        key_hash=key_hash,
        status="active",
        rate_limit=100,  # 100 requests/minute for demo
        user_email=request.user_email,
        role=request.role,
        created_at=timestamp,
        last_used_at=timestamp,
    )

    # Save to DynamoDB
    repository = ApiKeyRepository()
    await repository.create(api_key_model)

    return GenerateKeyResponse(
        key_id=key_id,
        api_key=api_key_plaintext,
        user_email=request.user_email,
        role=request.role,
        status="active",
        rate_limit=100,
        created_at=timestamp,
        warning=(
            "⚠️ DEMO ONLY: This endpoint is unauthenticated. "
            "Remove or protect it in production!"
        ),
    )
