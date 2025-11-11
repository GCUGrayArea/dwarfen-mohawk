"""Custom exception classes for the Zapier Triggers API."""

from typing import Any, Dict, Optional


class TriggerAPIException(Exception):
    """Base exception for Triggers API."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
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


class UnauthorizedError(TriggerAPIException):
    """Raised when authentication fails (401)."""

    def __init__(
        self,
        message: str = "Unauthorized: Invalid or missing API key",
        details: Optional[Dict[str, Any]] = None,
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


class ForbiddenError(TriggerAPIException):
    """Raised when access is denied (403)."""

    def __init__(
        self,
        message: str = "Forbidden: Access denied",
        details: Optional[Dict[str, Any]] = None,
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


class RateLimitError(TriggerAPIException):
    """Raised when rate limit is exceeded (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        details: Optional[Dict[str, Any]] = None,
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
