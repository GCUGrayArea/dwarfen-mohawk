"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from src.config import settings
from src.exceptions import TriggerAPIException
from src.handlers.exception_handler import (
    generic_exception_handler,
    trigger_api_exception_handler,
    validation_exception_handler,
)
from src.logging.config import configure_logging
from src.middleware.logging import LoggingMiddleware
from src.middleware.request_validation import RequestSizeValidationMiddleware
from src.routes import events, status

# Configure logging before creating the app
configure_logging()

# Create FastAPI application with enhanced metadata
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="""
## Zapier Triggers API

A unified event-driven automation system for the Zapier platform. This API
enables any system to send events into Zapier via a RESTful interface for
real-time, event-driven workflows.

### Key Features

- **Event Ingestion**: Send events with automatic deduplication (5-minute window)
- **Event Retrieval**: Poll inbox for undelivered events with cursor-based pagination
- **Event Acknowledgment**: Mark events as delivered after processing
- **Secure Authentication**: API key-based authentication on all endpoints
- **Rate Limiting**: Per-key rate limits to prevent abuse (default: 100 req/min)
- **Payload Validation**: Automatic validation of event structure and size limits

### Authentication

All API endpoints (except health checks) require authentication via API key:

```
Authorization: Bearer YOUR_API_KEY
```

API keys can be generated using the management CLI. Contact your administrator
for access.

### Rate Limits

- Default: 100 requests per minute per API key
- Custom limits available per key
- 429 responses include Retry-After header

### Event Lifecycle

1. **Ingest**: POST event → Receives unique event_id
2. **Retrieve**: GET inbox → Poll for undelivered events
3. **Acknowledge**: DELETE event → Mark as delivered (soft delete)
4. **Cleanup**: TTL-based deletion after 30 days (configurable)

### Need Help?

- See example code at [GitHub examples/](https://github.com/zapier/triggers-api/examples)
- Interactive API testing available below
- Contact support for API key management
""",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Zapier API Support",
        "url": "https://zapier.com/support",
        "email": "api-support@zapier.com",
    },
    license_info={
        "name": "Proprietary",
        "url": "https://zapier.com/terms",
    },
)

# Register middleware (order matters: first added = outermost layer)
# Request size validation should be first to reject oversized requests early
app.add_middleware(RequestSizeValidationMiddleware)
app.add_middleware(LoggingMiddleware)

# Register exception handlers
app.add_exception_handler(TriggerAPIException, trigger_api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Register routers
app.include_router(events.router)
app.include_router(status.router)


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """
    Root endpoint with API information.

    Returns:
        Dict with welcome message and docs link
    """
    return {
        "message": f"Welcome to {settings.api_title}",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/status",
    }
