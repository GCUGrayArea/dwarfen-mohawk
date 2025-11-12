"""Tests for logging middleware."""

import json
import uuid
from io import StringIO
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from src.middleware.logging import LoggingMiddleware


@pytest.fixture
def app_with_logging() -> FastAPI:
    """Create a test FastAPI app with logging middleware."""
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request) -> dict[str, str]:
        """Test endpoint that returns correlation ID."""
        return {"correlation_id": request.state.correlation_id}

    @app.get("/error")
    async def error_endpoint() -> None:
        """Test endpoint that raises an exception."""
        raise ValueError("Test error")

    return app


@pytest.mark.asyncio
async def test_logging_middleware_adds_correlation_id(
    app_with_logging: FastAPI,
) -> None:
    """Test that middleware adds correlation ID to request state."""
    transport = ASGITransport(app=app_with_logging)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test")

    assert response.status_code == 200
    data = response.json()
    assert "correlation_id" in data
    # Should be a valid UUID
    uuid.UUID(data["correlation_id"])


@pytest.mark.asyncio
async def test_logging_middleware_uses_existing_correlation_id(
    app_with_logging: FastAPI,
) -> None:
    """Test that middleware uses X-Request-ID header if provided."""
    correlation_id = str(uuid.uuid4())
    transport = ASGITransport(app=app_with_logging)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test", headers={"X-Request-ID": correlation_id})

    assert response.status_code == 200
    data = response.json()
    assert data["correlation_id"] == correlation_id


@pytest.mark.asyncio
async def test_logging_middleware_adds_correlation_id_to_response(
    app_with_logging: FastAPI,
) -> None:
    """Test that middleware adds X-Request-ID to response headers."""
    transport = ASGITransport(app=app_with_logging)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test")

    assert response.status_code == 200
    assert "x-request-id" in response.headers
    # Should be a valid UUID
    uuid.UUID(response.headers["x-request-id"])


@pytest.mark.asyncio
async def test_logging_middleware_logs_request_start(
    app_with_logging: FastAPI,
) -> None:
    """Test that middleware logs request start."""
    with patch("src.middleware.logging.logger") as mock_logger:
        transport = ASGITransport(app=app_with_logging)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/test?foo=bar")

        # Check that request start was logged
        assert mock_logger.info.call_count >= 1
        first_call = mock_logger.info.call_args_list[0]
        assert "Request started" in first_call[0]
        extra = first_call[1]["extra"]
        assert "correlation_id" in extra
        assert "context" in extra
        assert extra["context"]["method"] == "GET"
        assert extra["context"]["path"] == "/test"
        assert extra["context"]["query_params"] == {"foo": "bar"}


@pytest.mark.asyncio
async def test_logging_middleware_logs_response(
    app_with_logging: FastAPI,
) -> None:
    """Test that middleware logs response with status and timing."""
    with patch("src.middleware.logging.logger") as mock_logger:
        transport = ASGITransport(app=app_with_logging)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/test")

        # Check that response was logged
        assert mock_logger.info.call_count >= 2
        last_call = mock_logger.info.call_args_list[-1]
        assert "Request completed" in last_call[0]
        extra = last_call[1]["extra"]
        assert "correlation_id" in extra
        assert "context" in extra
        assert extra["context"]["status_code"] == 200
        assert "response_time_ms" in extra["context"]
        assert extra["context"]["response_time_ms"] >= 0


@pytest.mark.asyncio
async def test_logging_middleware_logs_errors(
    app_with_logging: FastAPI,
) -> None:
    """Test that middleware logs exceptions."""
    import contextlib

    with patch("src.middleware.logging.logger") as mock_logger:
        transport = ASGITransport(app=app_with_logging)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Error endpoint will raise, but we're testing logging
            with contextlib.suppress(Exception):
                await client.get("/error")

        # Check that error was logged
        assert mock_logger.error.call_count >= 1
        error_call = mock_logger.error.call_args_list[0]
        assert "Request failed with exception" in error_call[0]
        assert "exc_info" in error_call[1]


@pytest.mark.asyncio
async def test_json_formatter_output() -> None:
    """Test that JSONFormatter produces valid JSON."""
    import logging

    from src.logging.config import JSONFormatter, configure_logging

    # Configure logging
    configure_logging()

    # Capture log output
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("test_json_logger")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)

    # Log a message with extra context
    logger.info(
        "Test message",
        extra={
            "correlation_id": "test-correlation-id",
            "context": {"key": "value"},
        },
    )

    # Parse the log output as JSON
    log_output = log_stream.getvalue().strip()
    log_data = json.loads(log_output)

    # Verify JSON structure
    assert log_data["level"] == "INFO"
    assert log_data["message"] == "Test message"
    assert log_data["correlation_id"] == "test-correlation-id"
    assert log_data["key"] == "value"
    assert "timestamp" in log_data
    assert "logger" in log_data


@pytest.mark.asyncio
async def test_json_formatter_includes_exception_info() -> None:
    """Test that JSONFormatter includes exception details."""
    import logging

    from src.logging.config import JSONFormatter

    # Capture log output
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("test_exception_logger")
    logger.handlers = [handler]
    logger.setLevel(logging.ERROR)

    # Log an exception
    try:
        raise ValueError("Test exception")
    except ValueError:
        logger.error("Error occurred", exc_info=True)

    # Parse the log output as JSON
    log_output = log_stream.getvalue().strip()
    log_data = json.loads(log_output)

    # Verify exception is included
    assert "exception" in log_data
    assert "ValueError" in log_data["exception"]
    assert "Test exception" in log_data["exception"]


@pytest.mark.asyncio
async def test_json_formatter_debug_includes_location() -> None:
    """Test that JSONFormatter includes file location at DEBUG level."""
    import logging

    from src.logging.config import JSONFormatter

    # Capture log output
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("test_debug_logger")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)

    # Log at DEBUG level
    logger.debug("Debug message")

    # Parse the log output as JSON
    log_output = log_stream.getvalue().strip()
    log_data = json.loads(log_output)

    # Verify file location is included
    assert "file" in log_data
    assert "line" in log_data
    assert "function" in log_data
