"""Global exception handlers for consistent error responses."""

import json
import sys
import traceback
from typing import Any, Dict

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.exceptions import RateLimitError, TriggerAPIException


def create_error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: Dict[str, Any] = None,
) -> JSONResponse:
    """
    Create standardized error response.

    Args:
        error_code: Machine-readable error code
        message: Human-readable error message
        status_code: HTTP status code
        details: Additional error details

    Returns:
        JSONResponse with error information
    """
    content = {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "details": details or {},
    }

    return JSONResponse(status_code=status_code, content=content)


async def trigger_api_exception_handler(
    request: Request, exc: TriggerAPIException
) -> JSONResponse:
    """
    Handle custom TriggerAPIException.

    Args:
        request: FastAPI request
        exc: TriggerAPIException instance

    Returns:
        JSONResponse with error details
    """
    # Add Retry-After header for rate limit errors
    headers = {}
    if isinstance(exc, RateLimitError):
        headers["Retry-After"] = str(exc.retry_after)

    response = create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
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

    Formats validation errors into user-friendly messages.

    Args:
        request: FastAPI request
        exc: RequestValidationError from Pydantic

    Returns:
        JSONResponse with validation error details
    """
    errors = exc.errors()
    details = {"validation_errors": []}

    for error in errors:
        field = ".".join(str(loc) for loc in error["loc"])
        details["validation_errors"].append(
            {"field": field, "message": error["msg"], "type": error["type"]}
        )

    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Invalid request data",
        status_code=status.HTTP_400_BAD_REQUEST,
        details=details,
    )


async def request_too_large_handler(
    request: Request, exc: Exception
) -> JSONResponse:
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


async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Logs full traceback and returns generic error to client.

    Args:
        request: FastAPI request
        exc: Any unhandled exception

    Returns:
        JSONResponse with generic error message
    """
    # Log full exception details for debugging
    print(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")
    traceback.print_exception(type(exc), exc, exc.__traceback__)

    return create_error_response(
        error_code="INTERNAL_ERROR",
        message="An internal error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details={},
    )
