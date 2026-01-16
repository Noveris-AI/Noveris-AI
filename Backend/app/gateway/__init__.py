"""
AI Gateway Package.

The AI Gateway provides a unified OpenAI-compatible API for routing
requests to multiple upstream AI providers.

Features:
- OpenAI-compatible endpoints (/v1/chat/completions, /v1/embeddings, etc.)
- Multiple upstream provider support (OpenAI, vLLM, sglang, Cohere, etc.)
- Intelligent routing with fallback and load balancing
- Rate limiting and quota management
- API key authentication
- Request logging and observability
- SSRF protection

Architecture:
- Data Plane: Handles actual API requests and routes to upstreams
- Control Plane: Admin APIs for managing upstreams, routes, and keys

Usage:
    from app.gateway.routers import (
        openai_router,
        admin_upstreams_router,
        admin_api_keys_router,
    )

    # Mount data plane router (typically at root or separate service)
    app.include_router(openai_router)

    # Mount control plane routers
    app.include_router(admin_upstreams_router)
    app.include_router(admin_api_keys_router)
"""

from app.gateway.adapters import (
    AdapterBase,
    AdapterError,
    RouteContext,
    get_adapter,
)
from app.gateway.routing import (
    RoutingEngine,
    RoutingContext,
    NoRouteFoundError,
    NoHealthyUpstreamError,
)
from app.gateway.middleware import (
    GatewayAuthenticator,
    AuthContext,
    RateLimiter,
    SSRFGuard,
    TracingMiddleware,
)
from app.gateway.routers import (
    openai_router,
    admin_upstreams_router,
    admin_api_keys_router,
    admin_overview_router,
)

__all__ = [
    # Adapters
    "AdapterBase",
    "AdapterError",
    "RouteContext",
    "get_adapter",
    # Routing
    "RoutingEngine",
    "RoutingContext",
    "NoRouteFoundError",
    "NoHealthyUpstreamError",
    # Middleware
    "GatewayAuthenticator",
    "AuthContext",
    "RateLimiter",
    "SSRFGuard",
    "TracingMiddleware",
    # Routers
    "openai_router",
    "admin_upstreams_router",
    "admin_api_keys_router",
    "admin_overview_router",
]
