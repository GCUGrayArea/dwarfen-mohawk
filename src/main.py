"""FastAPI application entry point."""

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config import settings
from src.exceptions import TriggerAPIException
from src.handlers.exception_handler import (
    generic_exception_handler,
    trigger_api_exception_handler,
    validation_exception_handler,
)
from src.routes import events

# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Register exception handlers
app.add_exception_handler(TriggerAPIException, trigger_api_exception_handler)
app.add_exception_handler(
    RequestValidationError, validation_exception_handler
)
app.add_exception_handler(Exception, generic_exception_handler)

# Register routers
app.include_router(events.router)


@app.get("/status", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring and load balancers.

    Returns basic API status without authentication.

    Returns:
        Dict with status, version, and message
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "version": settings.api_version,
            "message": "Zapier Triggers API is running",
        },
    )


@app.get("/", tags=["Root"])
async def root() -> Dict[str, str]:
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
