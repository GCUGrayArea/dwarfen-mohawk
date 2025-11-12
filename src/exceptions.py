"""Custom exception classes for the Zapier Triggers API."""

from typing import Any


class TriggerAPIError(Exception):
    """Base exception for Triggers API."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize exception.

        Args:
            message: Human-readable error message
            status_code: HTTP status code
            error_code: Machine-readable error code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class UnauthorizedError(TriggerAPIError):
    """Raised when authentication fails (401)."""

    def __init__(
        self,
        message: str = "Unauthorized: Invalid or missing API key",
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize UnauthorizedError.

        Args:
            message: Error message
            details: Additional error details
        """
        super().__init__(
            message=message,
            status_code=401,
            error_code="UNAUTHORIZED",
            details=details,
        )


class ForbiddenError(TriggerAPIError):
    """Raised when access is denied (403)."""

    def __init__(
        self,
        message: str = "Forbidden: Access denied",
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize ForbiddenError.

        Args:
            message: Error message
            details: Additional error details
        """
        super().__init__(
            message=message,
            status_code=403,
            error_code="FORBIDDEN",
            details=details,
        )


class RateLimitError(TriggerAPIError):
    """Raised when rate limit is exceeded (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize RateLimitError.

        Args:
            message: Error message
            retry_after: Seconds until retry is allowed
            details: Additional error details
        """
        error_details = details or {}
        error_details["retry_after"] = retry_after
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details=error_details,
        )
        self.retry_after = retry_after


class EventNotFoundError(TriggerAPIError):
    """Raised when an event is not found (404)."""

    def __init__(
        self,
        message: str = "Event not found",
        event_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize EventNotFoundError.

        Args:
            message: Error message
            event_id: Event ID that was not found
            details: Additional error details
        """
        error_details = details or {}
        if event_id:
            error_details["event_id"] = event_id
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
            details=error_details,
        )


class ServiceUnavailableError(TriggerAPIError):
    """Raised when a dependent service is unavailable (503)."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        service: str | None = None,
        retry_after: int = 60,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize ServiceUnavailableError.

        Args:
            message: Error message
            service: Name of the unavailable service
            retry_after: Seconds until retry is recommended
            details: Additional error details
        """
        error_details = details or {}
        error_details["retry_after"] = retry_after
        if service:
            error_details["service"] = service
        super().__init__(
            message=message,
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            details=error_details,
        )


class RequestTooLargeError(TriggerAPIError):
    """Raised when request payload exceeds size limit (413)."""

    def __init__(
        self,
        message: str = "Request payload too large",
        max_size: str = "512KB",
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize RequestTooLargeError.

        Args:
            message: Error message
            max_size: Maximum allowed size
            details: Additional error details
        """
        error_details = details or {}
        error_details["max_size"] = max_size
        super().__init__(
            message=message,
            status_code=413,
            error_code="PAYLOAD_TOO_LARGE",
            details=error_details,
        )
