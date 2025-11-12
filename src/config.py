"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # DynamoDB Configuration
    dynamodb_endpoint_url: str | None = None
    dynamodb_table_events: str = "zapier-events"
    dynamodb_table_api_keys: str = "zapier-api-keys"

    # Application Configuration
    log_level: str = "INFO"
    api_title: str = "Zapier Triggers API"
    api_version: str = "1.0.0"
    api_description: str = "Event-driven automation REST API for Zapier platform"

    # Event Configuration
    event_ttl_days: int = 30
    deduplication_window_seconds: int = 300

    # API Limits
    max_request_size_bytes: int = 512 * 1024  # 512KB
    max_payload_size_bytes: int = 256 * 1024  # 256KB
    max_event_type_length: int = 255
    default_inbox_limit: int = 50
    max_inbox_limit: int = 200

    # Rate Limiting
    default_rate_limit_per_minute: int = 100


# Global settings instance
settings = Settings()
