"""Rate limiting middleware using in-memory counter (MVP)."""

import time
from collections import defaultdict
from typing import Dict, Tuple

from src.exceptions import RateLimitError


class RateLimiter:
    """
    Simple in-memory rate limiter.

    Tracks request counts per key_id per minute window.
    Note: This is not distributed and resets on restart (acceptable for MVP).
    """

    def __init__(self) -> None:
        """Initialize rate limiter with in-memory storage."""
        # key_id -> (request_count, window_start_time)
        self._requests: Dict[str, Tuple[int, float]] = defaultdict(
            lambda: (0, time.time())
        )
        self._window_seconds = 60  # 1 minute window

    def check_rate_limit(self, key_id: str, limit: int) -> None:
        """
        Check if request should be allowed based on rate limit.

        Args:
            key_id: API key identifier
            limit: Maximum requests allowed per minute

        Raises:
            RateLimitError: If rate limit is exceeded
        """
        current_time = time.time()
        count, window_start = self._requests[key_id]

        # Check if we need to reset the window
        if current_time - window_start >= self._window_seconds:
            # Start new window
            self._requests[key_id] = (1, current_time)
            return

        # Within current window
        if count >= limit:
            # Calculate retry_after
            time_remaining = int(
                self._window_seconds - (current_time - window_start)
            )
            retry_after = max(1, time_remaining)

            raise RateLimitError(
                message=f"Rate limit exceeded: {limit} requests/minute",
                retry_after=retry_after,
                details={
                    "limit": limit,
                    "window_seconds": self._window_seconds,
                },
            )

        # Increment counter
        self._requests[key_id] = (count + 1, window_start)

    def reset_key(self, key_id: str) -> None:
        """
        Reset rate limit counter for a specific key.

        Args:
            key_id: API key identifier to reset
        """
        if key_id in self._requests:
            del self._requests[key_id]

    def clear_all(self) -> None:
        """Clear all rate limit counters (useful for testing)."""
        self._requests.clear()


# Global rate limiter instance
rate_limiter = RateLimiter()
