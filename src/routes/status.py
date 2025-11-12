"""Health check and status endpoints."""

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.config import settings

# Module-level variable to track application start time
_app_start_time = time.time()

# Create router
router = APIRouter(tags=["Health"])


@router.get("/status")
async def get_status() -> JSONResponse:
    """
    Health check endpoint for monitoring and load balancers.

    Returns basic API status without authentication.
    Designed to be fast (< 10ms response time).

    Returns:
        JSONResponse with status, version, and uptime_seconds
    """
    current_time = time.time()
    uptime_seconds = int(current_time - _app_start_time)

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "version": settings.api_version,
            "uptime_seconds": uptime_seconds,
        },
    )
