"""
Deduplication cache for detecting duplicate events.

Uses in-memory storage with TTL-based expiration.
Suitable for single-instance deployments or MVP.
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional


class DeduplicationCache:
    """
    In-memory cache for event deduplication.

    Tracks event fingerprints within a time window to detect duplicates.
    Automatically cleans up expired entries on check operations.
    """

    def __init__(self, window_seconds: int = 300) -> None:
        """
        Initialize deduplication cache.

        Args:
            window_seconds: Deduplication time window (default: 300 = 5min)
        """
        self.window_seconds = window_seconds
        self._cache: Dict[str, tuple[str, float]] = {}

    def _generate_fingerprint(
        self, event_type: str, payload: Dict
    ) -> str:
        """
        Generate unique fingerprint for event.

        Args:
            event_type: Event type string
            payload: Event payload dictionary

        Returns:
            SHA256 hash of event content
        """
        content = json.dumps(
            {"event_type": event_type, "payload": payload},
            sort_keys=True,
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        now = time.time()
        expired_keys = [
            key
            for key, (_, expiry) in self._cache.items()
            if expiry < now
        ]
        for key in expired_keys:
            del self._cache[key]

    def check_and_add(
        self, event_type: str, payload: Dict, event_id: str
    ) -> Optional[str]:
        """
        Check if event is duplicate and add to cache.

        Args:
            event_type: Event type
            payload: Event payload
            event_id: Event UUID to store

        Returns:
            Existing event_id if duplicate, None if new event
        """
        self._cleanup_expired()

        fingerprint = self._generate_fingerprint(event_type, payload)

        if fingerprint in self._cache:
            existing_id, _ = self._cache[fingerprint]
            return existing_id

        expiry = time.time() + self.window_seconds
        self._cache[fingerprint] = (event_id, expiry)
        return None

    def clear(self) -> None:
        """Clear all cached entries (for testing)."""
        self._cache.clear()
