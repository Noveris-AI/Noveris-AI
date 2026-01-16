"""
Gateway Middleware Package.

This module provides middleware components for the AI Gateway:
- Authentication: API key validation and access control
- Rate Limiting: Redis-based request and token limits
- SSRF Guard: Protection against server-side request forgery
- Tracing: Request ID generation and distributed tracing

Usage:
    from app.gateway.middleware import (
        GatewayAuthenticator,
        RateLimiter,
        SSRFGuard,
        TracingMiddleware,
    )
"""

from app.gateway.middleware.auth import (
    GatewayAuthenticator,
    AuthContext,
    AuthenticationError,
    APIKeyGenerator,
    AccessControlChecker,
)
from app.gateway.middleware.rate_limit import (
    RateLimiter,
    RateLimitConfig,
    RateLimitResult,
    QuotaManager,
)
from app.gateway.middleware.ssrf_guard import (
    SSRFGuard,
    SSRFError,
    SSRFProtectedTransport,
    get_ssrf_guard,
    create_ssrf_protected_client,
)
from app.gateway.middleware.trace import (
    TracingMiddleware,
    RequestContext,
    RequestTimer,
    generate_request_id,
    generate_trace_id,
    get_request_id,
    get_trace_id,
    get_request_context,
    set_request_context,
)

__all__ = [
    # Authentication
    "GatewayAuthenticator",
    "AuthContext",
    "AuthenticationError",
    "APIKeyGenerator",
    "AccessControlChecker",
    # Rate Limiting
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitResult",
    "QuotaManager",
    # SSRF Protection
    "SSRFGuard",
    "SSRFError",
    "SSRFProtectedTransport",
    "get_ssrf_guard",
    "create_ssrf_protected_client",
    # Tracing
    "TracingMiddleware",
    "RequestContext",
    "RequestTimer",
    "generate_request_id",
    "generate_trace_id",
    "get_request_id",
    "get_trace_id",
    "get_request_context",
    "set_request_context",
]
