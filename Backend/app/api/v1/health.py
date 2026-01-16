"""
Health check and system status endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text

from app.api.v1.auth import get_redis
from app.core.config import settings
from app.core.database import engine
from app.schemas.auth import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.

    Returns the service status without checking dependencies.
    """
    return HealthResponse(
        status="healthy",
        version=settings.app.app_version,
    )


@router.get("/health", response_model=HealthResponse)
async def health_detailed(redis=Depends(get_redis)):
    """
    Detailed health check with dependency status.
    """
    import sys
    db_status = "unhealthy"
    redis_status = "unhealthy"

    # Check database
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        print(f"DB error: {e}", file=sys.stderr)

    # Check Redis
    try:
        await redis.ping()
        redis_status = "healthy"
    except Exception as e:
        print(f"Redis error: {e}", file=sys.stderr)

    overall_status = "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.app.app_version,
        database=db_status,
        redis=redis_status,
    )


@router.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": settings.app.app_name,
        "version": settings.app.app_version,
        "environment": settings.app.app_env,
        "docs_url": "/docs" if settings.docs_enabled else None,
        "api_v1": "/api/v1",
    }
