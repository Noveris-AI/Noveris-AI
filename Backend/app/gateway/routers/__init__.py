"""
Gateway Routers Package.

This module provides the FastAPI routers for the AI Gateway:
- Data Plane: OpenAI-compatible API endpoints (/v1/*)
- Control Plane: Admin API endpoints (/api/gateway/*)

Usage:
    from app.gateway.routers import (
        openai_router,
        admin_upstreams_router,
        admin_api_keys_router,
    )

    app.include_router(openai_router)
    app.include_router(admin_upstreams_router)
    app.include_router(admin_api_keys_router)
"""

from app.gateway.routers.openai_compat import router as openai_router
from app.gateway.routers.admin_upstreams import router as admin_upstreams_router
from app.gateway.routers.admin_api_keys import router as admin_api_keys_router
from app.gateway.routers.admin_overview import router as admin_overview_router

__all__ = [
    "openai_router",
    "admin_upstreams_router",
    "admin_api_keys_router",
    "admin_overview_router",
]
