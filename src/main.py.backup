"""FastAPI application entry point."""

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.config import settings

# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    docs_url="/docs",
    redoc_url="/redoc",
)


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
