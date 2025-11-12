"""Logging configuration with JSON formatting."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from src.config import settings


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON.

    Each log record is formatted as a JSON object with the following fields:
    - timestamp: ISO 8601 timestamp in UTC
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - logger: Logger name
    - message: Log message
    - correlation_id: Request correlation ID (if present in extra)
    - Additional fields from the `extra` dict passed to logger calls
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log record
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation_id if present
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

        # Add any additional context from extra
        if hasattr(record, "context"):
            log_data.update(record.context)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add file location for debugging (only at DEBUG level)
        if record.levelno == logging.DEBUG:
            log_data["file"] = record.pathname
            log_data["line"] = record.lineno
            log_data["function"] = record.funcName

        return json.dumps(log_data)


def configure_logging() -> None:
    """
    Configure application logging with JSON formatter.

    Sets up the root logger to output structured JSON logs to stdout.
    Log level is determined by the LOG_LEVEL environment variable.
    """
    # Get log level from settings
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(JSONFormatter())

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Log configuration complete
    root_logger.info(
        "Logging configured",
        extra={"context": {"log_level": settings.log_level}},
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: The name of the logger (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
