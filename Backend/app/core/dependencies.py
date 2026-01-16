"""
Dependency injection utilities for FastAPI.
"""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer
from redis.asyncio import Redis

from app.core.config import settings
from app.core.database import AsyncSession, get_db
from app.core.session import SessionData, SessionManager

# Security scheme for OpenAPI docs
security = HTTPBearer(auto_error=False)


# ============================================================================
# Redis Dependency
# ============================================================================

# Global Redis connection pool (singleton pattern)
_redis_pool: Redis | None = None

async def get_redis_pool() -> Redis:
    """
    Get or create global Redis connection pool.

    This ensures we reuse the same connection pool across all requests
    instead of creating a new connection for each request.
    """
    global _redis_pool

    if _redis_pool is None:
        _redis_pool = Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password if settings.redis.password else None,
            db=settings.redis.db,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.redis.pool_size,
        )
        # Test connection
        try:
            await _redis_pool.ping()
        except Exception as e:
            _redis_pool = None
            raise RuntimeError(f"Failed to connect to Redis: {e}")

    return _redis_pool

async def get_redis() -> Redis:
    """
    Get Redis client for dependency injection.

    Returns the shared connection pool instead of creating new connections.
    """
    return await get_redis_pool()


# Type alias for Redis dependency
RedisDep = Annotated[Redis, Depends(get_redis)]


# ============================================================================
# Session Manager Dependency
# ============================================================================

async def get_session_manager(redis: RedisDep) -> SessionManager:
    """
    Get session manager for dependency injection.
    """
    return SessionManager(redis)


# Type alias for SessionManager dependency
SessionManagerDep = Annotated[SessionManager, Depends(get_session_manager)]


# ============================================================================
# Current User Dependency
# ============================================================================

async def get_current_user_optional(
    request: Request,
    response: Response,
    session_manager: SessionManagerDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[SessionData]:
    """
    Get current user from session cookie (optional).

    Returns None if not authenticated, doesn't raise exception.
    """
    # Skip authentication for OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        return None

    session_id = request.cookies.get(settings.session.cookie_name)

    # DEBUG: Log cookie check
    import structlog
    logger = structlog.get_logger(__name__)
    logger.info(
        "Checking auth session",
        method=request.method,
        session_id=session_id[:20] + "..." if session_id else None,
        cookie_name=settings.session.cookie_name,
        all_cookies=list(request.cookies.keys()),
        path=request.url.path,
        cookie_header=request.headers.get("cookie"),
        origin=request.headers.get("origin"),
        referer=request.headers.get("referer"),
    )

    if not session_id:
        logger.warning("No session cookie found", path=request.url.path)
        return None

    session = await session_manager.get(session_id)

    if not session:
        # Clear invalid cookie
        response.delete_cookie(
            settings.session.cookie_name,
            domain=settings.session.cookie_domain or None,
            path="/",
        )
        return None

    # Verify user still exists in database
    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(
        select(User).where(User.id == session.user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user:
        await session_manager.destroy(session_id)
        response.delete_cookie(
            settings.session.cookie_name,
            domain=settings.session.cookie_domain or None,
            path="/",
        )
        return None

    # Conditional session extension: only extend if less than half TTL remaining
    if settings.session.extend_on_activity:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        time_until_expiry = (session.expires_at - now).total_seconds()
        ttl = settings.session.remember_ttl if session.remember_me else settings.session.ttl

        # Only extend if less than 50% of TTL remains (reduces Redis writes)
        if time_until_expiry < (ttl / 2):
            await session_manager.extend(session_id)

    return session


async def get_current_user(
    session_data: Annotated[Optional[SessionData], Depends(get_current_user_optional)],
) -> SessionData:
    """
    Get current authenticated user.

    Raises 401 if not authenticated.
    """
    if session_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Session"},
        )

    return session_data


# Type aliases for current user dependencies
CurrentUserDep = Annotated[SessionData, Depends(get_current_user)]
OptionalUserDep = Annotated[Optional[SessionData], Depends(get_current_user_optional)]


# ============================================================================
# CSRF Token Dependency
# ============================================================================

async def get_csrf_token(request: Request) -> Optional[str]:
    """
    Get CSRF token from request.

    Checks both header and cookie.
    """
    # Check header first
    token = request.headers.get(settings.csrf.header_name)

    # Fall back to cookie
    if not token:
        token = request.cookies.get(settings.csrf.cookie_name)

    return token


CsrfTokenDep = Annotated[Optional[str], Depends(get_csrf_token)]


# ============================================================================
# Client Info Dependencies
# ============================================================================

async def get_client_ip(request: Request) -> str:
    """
    Get client IP address from request.

    Handles proxies and X-Forwarded-For header.
    """
    # Check for X-Forwarded-For header (proxy/load balancer)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # Take the first IP (original client)
        return x_forwarded_for.split(",")[0].strip()

    # Fall back to direct connection
    client_host = request.client.host if request.client else "unknown"
    return client_host


async def get_user_agent(request: Request) -> Optional[str]:
    """
    Get User-Agent from request.
    """
    return request.headers.get("User-Agent")


# Type aliases
ClientIpDep = Annotated[str, Depends(get_client_ip)]
UserAgentDep = Annotated[Optional[str], Depends(get_user_agent)]


# ============================================================================
# Common Dependencies
# ============================================================================

async def get_request_id(request: Request) -> str:
    """
    Get or generate request ID for tracing.
    """
    request_id = request.headers.get("X-Request-ID")
    if request_id:
        return request_id

    # Generate unique ID
    import uuid
    return str(uuid.uuid4())


RequestIdDep = Annotated[str, Depends(get_request_id)]


# ============================================================================
# Tenant ID Dependency
# ============================================================================

import uuid

async def get_tenant_id(
    current_user: Annotated[SessionData, Depends(get_current_user)],
) -> uuid.UUID:
    """
    Get tenant ID from current user session.

    For single-tenant deployments, falls back to DEFAULT_TENANT_ID.
    """
    # Try to get tenant_id from session data
    if hasattr(current_user, 'tenant_id') and current_user.tenant_id:
        return current_user.tenant_id

    # Fall back to default tenant ID for single-tenant deployments
    default_tenant = getattr(settings, 'default_tenant_id', None)
    if default_tenant:
        return uuid.UUID(default_tenant) if isinstance(default_tenant, str) else default_tenant

    # Ultimate fallback
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


TenantIdDep = Annotated[uuid.UUID, Depends(get_tenant_id)]
