"""API routes for event operations."""


from fastapi import APIRouter, Depends, Query, Request, status

from src.auth.dependencies import require_api_key
from src.middleware.rate_limit import rate_limiter
from src.models.api_key import ApiKey
from src.schemas.event import (
    CreateEventRequest,
    EventResponse,
    InboxResponse,
)
from src.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Event successfully ingested",
            "content": {
                "application/json": {
                    "example": {
                        "status": "accepted",
                        "event_id": "550e8400-e29b-41d4-a716-446655440000",
                        "timestamp": "2025-11-11T12:00:00Z",
                        "message": "Event successfully ingested",
                    }
                }
            },
        },
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "error_code": "VALIDATION_ERROR",
                        "message": "Invalid request data",
                        "details": {
                            "field": "event_type",
                            "error": "Field required",
                        },
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized - Missing or invalid API key",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "error_code": "UNAUTHORIZED",
                        "message": "Invalid or missing API key",
                        "details": {},
                    }
                }
            },
        },
        413: {
            "description": "Payload too large",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "error_code": "PAYLOAD_TOO_LARGE",
                        "message": "Request payload exceeds maximum size",
                        "details": {"max_size": "512KB"},
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "message": "Rate limit exceeded",
                        "details": {"retry_after": 60},
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "error_code": "INTERNAL_ERROR",
                        "message": "An internal error occurred",
                        "details": {},
                    }
                }
            },
        },
    },
)
async def create_event(
    request: Request,
    event_request: CreateEventRequest,
    api_key: ApiKey = Depends(require_api_key),
) -> EventResponse:
    """
    Ingest a new event into the system.

    Validates the event payload, checks for duplicates within a 5-minute
    window, generates a unique event ID, and persists the event to DynamoDB.

    Args:
        request: FastAPI request object
        event_request: Event data to ingest
        api_key: Authenticated API key (injected by dependency)

    Returns:
        EventResponse with event ID, timestamp, and status

    Raises:
        UnauthorizedError: If API key is missing or invalid (401)
        RateLimitError: If rate limit is exceeded (429)
        ValidationError: If event data is invalid (400)
        PayloadTooLargeError: If payload exceeds size limits (413)
    """
    # Check rate limit (raises RateLimitError if exceeded)
    rate_limiter.check_rate_limit(api_key.key_id, api_key.rate_limit)

    # Create service and ingest event
    service = EventService()
    response = await service.ingest(event_request)

    return response


@router.get(
    "/inbox",
    response_model=InboxResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of undelivered events",
            "content": {
                "application/json": {
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
            },
        },
        401: {
            "description": "Unauthorized - Missing or invalid API key",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "error_code": "UNAUTHORIZED",
                        "message": "Invalid or missing API key",
                        "details": {},
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "message": "Rate limit exceeded",
                        "details": {"retry_after": 60},
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "error_code": "INTERNAL_ERROR",
                        "message": "An internal error occurred",
                        "details": {},
                    }
                }
            },
        },
    },
)
async def get_inbox(
    request: Request,
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of events to return (1-200)",
    ),
    cursor: str | None = Query(
        default=None,
        description="Pagination cursor from previous response",
    ),
    api_key: ApiKey = Depends(require_api_key),
) -> InboxResponse:
    """
    List undelivered events with pagination.

    Returns events in chronological order (oldest first) with cursor-based
    pagination. Use the next_cursor from the response to fetch the next page.

    Args:
        request: FastAPI request object
        limit: Maximum events to return (default 50, max 200)
        cursor: Opaque pagination cursor (None for first page)
        api_key: Authenticated API key (injected by dependency)

    Returns:
        InboxResponse with list of events and pagination metadata

    Raises:
        UnauthorizedError: If API key is missing or invalid (401)
        RateLimitError: If rate limit is exceeded (429)
    """
    # Check rate limit (raises RateLimitError if exceeded)
    rate_limiter.check_rate_limit(api_key.key_id, api_key.rate_limit)

    # Create service and list inbox
    service = EventService()
    response = await service.list_inbox(limit=limit, cursor=cursor)

    return response


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Event retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "event_id": "550e8400-e29b-41d4-a716-446655440000",
                        "timestamp": "2025-11-11T12:00:00Z",
                        "message": "Event retrieved successfully",
                        "event_type": "user.signup",
                        "payload": {"user_id": "123"},
                        "source": "web-app",
                        "delivered": False,
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized - Missing or invalid API key",
        },
        404: {
            "description": "Event not found",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "error_code": "NOT_FOUND",
                        "message": "Event not found",
                        "details": {},
                    }
                }
            },
        },
    },
)
async def get_event(
    event_id: str,
    timestamp: str,
    api_key: ApiKey = Depends(require_api_key),
) -> EventResponse:
    """
    Retrieve a specific event by ID and timestamp.

    Args:
        event_id: Event UUID
        timestamp: Event ISO 8601 timestamp
        api_key: Authenticated API key (injected by dependency)

    Returns:
        EventResponse with full event details

    Raises:
        UnauthorizedError: If API key is missing or invalid (401)
        EventNotFoundError: If event does not exist (404)
    """
    from src.exceptions import EventNotFoundError

    service = EventService()
    response = await service.get(event_id, timestamp)

    if response is None:
        raise EventNotFoundError(
            message=f"Event {event_id} not found",
            event_id=event_id,
        )

    return response


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {
            "description": "Event marked as delivered (no content returned)",
        },
        401: {
            "description": "Unauthorized - Missing or invalid API key",
        },
        404: {
            "description": "Event not found",
        },
    },
)
async def delete_event(
    event_id: str,
    timestamp: str,
    api_key: ApiKey = Depends(require_api_key),
) -> None:
    """
    Mark an event as delivered (soft delete).

    This operation is idempotent - deleting an already-delivered event
    returns 204.

    Args:
        event_id: Event UUID
        timestamp: Event ISO 8601 timestamp
        api_key: Authenticated API key (injected by dependency)

    Returns:
        None (204 No Content)

    Raises:
        UnauthorizedError: If API key is missing or invalid (401)
        EventNotFoundError: If event does not exist (404)
    """
    from src.exceptions import EventNotFoundError

    service = EventService()
    result = await service.mark_delivered(event_id, timestamp)

    if not result:
        raise EventNotFoundError(
            message=f"Event {event_id} not found",
            event_id=event_id,
        )

    return None
