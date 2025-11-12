"""Request logging middleware with correlation ID support."""

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.logging.config import get_logger

logger = get_logger(__name__)


def _get_or_generate_correlation_id(request: Request) -> str:
    """
    Extract or generate a correlation ID for the request.

    Args:
        request: The incoming request

    Returns:
        The correlation ID (from header or newly generated)
    """
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def _log_request_start(request: Request, correlation_id: str) -> None:
    """
    Log the start of a request.

    Args:
        request: The incoming request
        correlation_id: The correlation ID for this request
    """
    logger.info(
        "Request started",
        extra={
            "correlation_id": correlation_id,
            "context": {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
            },
        },
    )


def _log_request_error(
    request: Request, correlation_id: str, exc: Exception, elapsed_ms: float
) -> None:
    """
    Log a request that failed with an exception.

    Args:
        request: The incoming request
        correlation_id: The correlation ID for this request
        exc: The exception that was raised
        elapsed_ms: Time elapsed before the exception
    """
    logger.error(
        "Request failed with exception",
        exc_info=exc,
        extra={
            "correlation_id": correlation_id,
            "context": {
                "method": request.method,
                "path": request.url.path,
                "response_time_ms": elapsed_ms,
            },
        },
    )


def _log_request_complete(
    request: Request, response: Response, correlation_id: str, elapsed_ms: float
) -> None:
    """
    Log the completion of a request.

    Args:
        request: The incoming request
        response: The response being returned
        correlation_id: The correlation ID for this request
        elapsed_ms: Time elapsed during request processing
    """
    # Extract API key ID if present (hashed, never the actual key)
    api_key_id = getattr(request.state, "api_key_id", None)

    logger.info(
        "Request completed",
        extra={
            "correlation_id": correlation_id,
            "context": {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "response_time_ms": round(elapsed_ms, 2),
                "api_key_id": api_key_id,
            },
        },
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all HTTP requests and responses.

    Features:
    - Adds unique correlation ID (X-Request-ID) to each request
    - Logs request start with method, path, and correlation ID
    - Logs response with status code, response time, and correlation ID
    - Masks sensitive headers (Authorization) from logs
    - Includes API key ID (hashed) if authentication is present
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and add logging.

        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain

        Returns:
            The response from the handler
        """
        # Generate or extract correlation ID
        correlation_id = _get_or_generate_correlation_id(request)
        request.state.correlation_id = correlation_id

        # Log request start and track timing
        start_time = time.time()
        _log_request_start(request, correlation_id)

        # Process request with error handling
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = (time.time() - start_time) * 1000
            _log_request_error(request, correlation_id, exc, elapsed_ms)
            raise

        # Log successful completion
        elapsed_ms = (time.time() - start_time) * 1000
        _log_request_complete(request, response, correlation_id, elapsed_ms)

        # Add correlation ID to response headers
        response.headers["X-Request-ID"] = correlation_id

        return response
