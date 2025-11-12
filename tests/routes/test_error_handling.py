"""Comprehensive error handling tests."""

import json
from unittest.mock import AsyncMock

import pytest

from src.exceptions import (
    EventNotFoundError,
    RequestTooLargeError,
)


@pytest.mark.asyncio
async def test_validation_error_includes_correlation_id() -> None:
    """Test that validation errors include correlation ID."""
    from unittest.mock import AsyncMock

    from fastapi import Request
    from fastapi.exceptions import RequestValidationError

    from src.handlers.exception_handler import validation_exception_handler

    # Create mock request with correlation ID
    mock_request = AsyncMock(spec=Request)
    mock_request.state.correlation_id = "test-correlation-id"

    # Create validation error
    exc = RequestValidationError(
        errors=[
            {"loc": ("body", "event_type"), "msg": "field required", "type": "missing"}
        ]
    )

    # Handle the exception
    response = await validation_exception_handler(mock_request, exc)

    assert response.status_code == 400
    data = json.loads(response.body)
    assert data["correlation_id"] == "test-correlation-id"
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "validation_errors" in data["details"]


@pytest.mark.asyncio
async def test_validation_error_has_actionable_messages() -> None:
    """Test that validation errors have clear, actionable messages."""
    from unittest.mock import AsyncMock

    from fastapi import Request
    from fastapi.exceptions import RequestValidationError

    from src.handlers.exception_handler import validation_exception_handler

    # Create mock request
    mock_request = AsyncMock(spec=Request)
    mock_request.state.correlation_id = "test-correlation-id"

    # Create validation error with multiple fields
    exc = RequestValidationError(
        errors=[
            {"loc": ("body", "event_type"), "msg": "field required", "type": "missing"},
            {
                "loc": ("body", "payload"),
                "msg": "value is not a valid dict",
                "type": "type_error.dict",
            },
        ]
    )

    # Handle the exception
    response = await validation_exception_handler(mock_request, exc)

    assert response.status_code == 400
    data = json.loads(response.body)

    # Check that message summarizes the error
    assert "message" in data
    assert len(data["message"]) > 0

    # Check validation_errors format
    validation_errors = data["details"]["validation_errors"]
    assert len(validation_errors) == 2

    for error in validation_errors:
        assert "field" in error
        assert "message" in error
        assert "type" in error
        # Field should not include 'body' prefix
        assert not error["field"].startswith("body")


@pytest.mark.asyncio
async def test_rate_limit_error_includes_retry_after_header() -> None:
    """Test that rate limit errors include Retry-After header."""
    from fastapi import Request

    from src.exceptions import RateLimitError
    from src.handlers.exception_handler import trigger_api_exception_handler

    # Create mock request
    mock_request = AsyncMock(spec=Request)
    mock_request.state.correlation_id = "test-correlation-id"

    # Create rate limit error
    exc = RateLimitError(
        message="Rate limit exceeded: 100 requests/minute",
        retry_after=45,
    )

    # Handle the exception
    response = await trigger_api_exception_handler(mock_request, exc)

    # Check response
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert response.headers["Retry-After"] == "45"

    # Check body
    body = json.loads(response.body)
    assert body["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert body["correlation_id"] == "test-correlation-id"
    assert body["details"]["retry_after"] == 45


@pytest.mark.asyncio
async def test_request_too_large_error() -> None:
    """Test that RequestTooLargeError returns proper 413 response."""
    from unittest.mock import AsyncMock

    from fastapi import Request

    from src.handlers.exception_handler import trigger_api_exception_handler

    # Create mock request
    mock_request = AsyncMock(spec=Request)
    mock_request.state.correlation_id = "test-correlation-id"

    exc = RequestTooLargeError(
        message="Request size 600.0KB exceeds maximum 512KB",
        max_size="512KB",
        details={
            "request_size": "600.0KB",
            "max_size": "512KB",
        },
    )

    # Handle the exception
    response = await trigger_api_exception_handler(mock_request, exc)

    assert response.status_code == 413
    data = json.loads(response.body)
    assert data["error_code"] == "PAYLOAD_TOO_LARGE"
    assert data["correlation_id"] == "test-correlation-id"
    assert "max_size" in data["details"]
    assert "request_size" in data["details"]


@pytest.mark.asyncio
async def test_service_unavailable_error() -> None:
    """Test that service errors return 503."""
    from fastapi import Request

    from src.handlers.exception_handler import generic_exception_handler

    # Create mock request
    mock_request = AsyncMock(spec=Request)
    mock_request.state.correlation_id = "test-correlation-id"
    mock_request.method = "POST"
    mock_request.url.path = "/events"

    # Simulate a connection error
    exc = ConnectionError("Unable to connect to DynamoDB")

    # Handle the exception
    response = await generic_exception_handler(mock_request, exc)

    # Check response
    assert response.status_code == 503
    body = json.loads(response.body)
    assert body["error_code"] == "SERVICE_UNAVAILABLE"
    assert body["correlation_id"] == "test-correlation-id"
    assert "retry_after" in body["details"]


@pytest.mark.asyncio
async def test_internal_error_includes_correlation_id() -> None:
    """Test that internal errors include correlation ID."""
    from fastapi import Request

    from src.handlers.exception_handler import generic_exception_handler

    # Create mock request
    mock_request = AsyncMock(spec=Request)
    mock_request.state.correlation_id = "test-correlation-id"
    mock_request.method = "GET"
    mock_request.url.path = "/test"

    # Simulate an unexpected error
    exc = ValueError("Unexpected error")

    # Handle the exception
    response = await generic_exception_handler(mock_request, exc)

    # Check response
    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["correlation_id"] == "test-correlation-id"
    assert "contact support" in body["message"].lower()


@pytest.mark.asyncio
async def test_error_response_without_correlation_id() -> None:
    """Test that errors work even without correlation ID."""
    from fastapi import Request

    from src.exceptions import UnauthorizedError
    from src.handlers.exception_handler import trigger_api_exception_handler

    # Create mock request without correlation ID
    mock_request = AsyncMock(spec=Request)
    mock_request.state = AsyncMock()
    type(mock_request.state).correlation_id = property(lambda self: None)

    exc = UnauthorizedError()

    # Handle the exception
    response = await trigger_api_exception_handler(mock_request, exc)

    # Should not fail, just exclude correlation_id
    assert response.status_code == 401
    body = json.loads(response.body)
    assert body["error_code"] == "UNAUTHORIZED"
    # correlation_id should not be in body if not available
    assert "correlation_id" not in body or body["correlation_id"] is None


@pytest.mark.asyncio
async def test_dynamodb_timeout_returns_503() -> None:
    """Test that DynamoDB timeout errors return 503."""

    from fastapi import Request

    from src.handlers.exception_handler import generic_exception_handler

    # Create mock request
    mock_request = AsyncMock(spec=Request)
    mock_request.state.correlation_id = "test-correlation-id"
    mock_request.method = "GET"
    mock_request.url.path = "/inbox"

    # Simulate a timeout error
    exc = TimeoutError("DynamoDB request timed out")

    # Handle the exception
    response = await generic_exception_handler(mock_request, exc)

    # Check response
    assert response.status_code == 503
    body = json.loads(response.body)
    assert body["error_code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_validation_error_with_multiple_fields() -> None:
    """Test that validation errors with multiple fields are formatted clearly."""
    from unittest.mock import AsyncMock

    from fastapi import Request
    from fastapi.exceptions import RequestValidationError

    from src.handlers.exception_handler import validation_exception_handler

    # Create mock request
    mock_request = AsyncMock(spec=Request)
    mock_request.state.correlation_id = "test-correlation-id"

    # Create validation error with 3 fields
    exc = RequestValidationError(
        errors=[
            {
                "loc": ("body", "event_type"),
                "msg": "ensure this value has at least 1 characters",
                "type": "value_error.any_str.min_length",
            },
            {
                "loc": ("body", "payload"),
                "msg": "value is not a valid dict",
                "type": "type_error.dict",
            },
            {"loc": ("body", "timestamp"), "msg": "field required", "type": "missing"},
        ]
    )

    # Handle the exception
    response = await validation_exception_handler(mock_request, exc)

    assert response.status_code == 400
    data = json.loads(response.body)

    # Message should mention multiple errors
    assert (
        "more errors" in data["message"].lower() or "errors" in data["message"].lower()
    )

    # Should have multiple validation errors
    validation_errors = data["details"]["validation_errors"]
    assert len(validation_errors) == 3
    fields = [err["field"] for err in validation_errors]

    # Check that we have errors for different fields
    assert len(set(fields)) == 3


@pytest.mark.asyncio
async def test_event_not_found_error_format() -> None:
    """Test EventNotFoundError returns proper 404 response."""
    from fastapi import Request

    from src.handlers.exception_handler import trigger_api_exception_handler

    # Create mock request
    mock_request = AsyncMock(spec=Request)
    mock_request.state.correlation_id = "test-correlation-id"

    exc = EventNotFoundError(
        message="Event not found",
        event_id="test-event-123",
    )

    # Handle the exception
    response = await trigger_api_exception_handler(mock_request, exc)

    # Check response
    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error_code"] == "NOT_FOUND"
    assert body["correlation_id"] == "test-correlation-id"
    assert body["details"]["event_id"] == "test-event-123"
