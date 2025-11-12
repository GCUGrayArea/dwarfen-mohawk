"""Request validation middleware."""

from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings
from src.exceptions import RequestTooLargeError


class RequestSizeValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate request size before processing.

    Prevents large requests from consuming resources during parsing.
    Returns 413 Payload Too Large for oversized requests.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Validate request size and process request.

        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain

        Returns:
            The response from the handler

        Raises:
            RequestTooLargeError: If request exceeds size limit
        """
        # Extract correlation ID early so it's available for error responses
        import uuid

        correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id

        # Check Content-Length header
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)
                max_size = settings.max_request_size_bytes

                if size > max_size:
                    # Calculate size in KB for error message
                    size_kb = size / 1024
                    max_kb = max_size / 1024

                    raise RequestTooLargeError(
                        message=f"Request size {size_kb:.1f}KB exceeds maximum {max_kb:.0f}KB",
                        max_size=f"{max_kb:.0f}KB",
                        details={
                            "request_size": f"{size_kb:.1f}KB",
                            "max_size": f"{max_kb:.0f}KB",
                        },
                    )
            except ValueError:
                # Invalid Content-Length header, let it pass for now
                pass

        # Process request normally
        response = await call_next(request)
        return response
