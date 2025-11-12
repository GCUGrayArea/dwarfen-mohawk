"""Global exception handlers for consistent error responses."""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.exceptions import RateLimitError, TriggerAPIError


def create_error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> JSONResponse:
    """
    Create standardized error response.

    Args:
        error_code: Machine-readable error code
        message: Human-readable error message
        status_code: HTTP status code
        details: Additional error details
        correlation_id: Request correlation ID for tracing

    Returns:
        JSONResponse with error information
    """
    content = {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "details": details or {},
    }

    # Add correlation ID if provided
    if correlation_id:
        content["correlation_id"] = correlation_id

    return JSONResponse(status_code=status_code, content=content)


async def trigger_api_exception_handler(
    request: Request, exc: TriggerAPIError
) -> JSONResponse:
    """
    Handle custom TriggerAPIError.

    Args:
        request: FastAPI request
        exc: TriggerAPIError instance

    Returns:
        JSONResponse with error details
    """
    # Get correlation ID from request state
    correlation_id = getattr(request.state, "correlation_id", None)

    # Add Retry-After header for rate limit errors
    headers = {}
    if isinstance(exc, RateLimitError):
        headers["Retry-After"] = str(exc.retry_after)

    response = create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        correlation_id=correlation_id,
    )

    # Add headers after creation
    for key, value in headers.items():
        response.headers[key] = value

    return response


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors from FastAPI.

    Formats validation errors into user-friendly, actionable messages.

    Args:
        request: FastAPI request
        exc: RequestValidationError from Pydantic

    Returns:
        JSONResponse with validation error details
    """
    # Get correlation ID from request state
    correlation_id = getattr(request.state, "correlation_id", None)

    errors = exc.errors()
    details: dict[str, Any] = {"validation_errors": []}
    error_messages = []

    for error in errors:
        # Build field path (skip 'body' prefix for cleaner messages)
        field_parts = [str(loc) for loc in error["loc"] if loc != "body"]
        field = ".".join(field_parts) if field_parts else "request"

        # Create actionable error message
        msg = error["msg"]
        error_type = error["type"]

        # Enhance message with more context
        if error_type == "missing":
            msg = "Field is required"
        elif error_type == "value_error":
            msg = f"Invalid value: {msg}"

        details["validation_errors"].append(
            {"field": field, "message": msg, "type": error_type}
        )
        error_messages.append(f"{field}: {msg}")

    # Create summary message with first error
    summary = error_messages[0] if error_messages else "Invalid request data"
    if len(error_messages) > 1:
        summary += f" (and {len(error_messages) - 1} more errors)"

    return create_error_response(
        error_code="VALIDATION_ERROR",
        message=summary,
        status_code=status.HTTP_400_BAD_REQUEST,
        details=details,
        correlation_id=correlation_id,
    )


async def request_too_large_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle request body too large errors.

    Args:
        request: FastAPI request
        exc: Exception from request parsing

    Returns:
        JSONResponse with payload size error
    """
    return create_error_response(
        error_code="PAYLOAD_TOO_LARGE",
        message="Request payload exceeds maximum size of 512KB",
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        details={"max_size": "512KB"},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Logs full traceback and returns generic error to client.
    Implements graceful degradation for service errors.

    Args:
        request: FastAPI request
        exc: Any unhandled exception

    Returns:
        JSONResponse with generic error message
    """
    # Get correlation ID from request state
    correlation_id = getattr(request.state, "correlation_id", None)

    # Log full exception details for debugging with correlation ID
    from src.logging.config import get_logger

    logger = get_logger(__name__)
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        exc_info=exc,
        extra={
            "correlation_id": correlation_id,
            "context": {
                "exception_type": type(exc).__name__,
                "method": request.method,
                "path": request.url.path,
            },
        },
    )

    # Check for DynamoDB/service unavailability errors
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__

    # DynamoDB connection errors should return 503
    if any(
        keyword in exc_str for keyword in ["connection", "timeout", "unavailable"]
    ) or any(keyword in exc_type for keyword in ["ConnectionError", "TimeoutError"]):
        return create_error_response(
            error_code="SERVICE_UNAVAILABLE",
            message="Service temporarily unavailable. Please try again later.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"retry_after": 60},
            correlation_id=correlation_id,
        )

    # Generic internal error for other exceptions
    return create_error_response(
        error_code="INTERNAL_ERROR",
        message="An internal error occurred. Please contact support with the correlation ID.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details={},
        correlation_id=correlation_id,
    )
