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

async def get_redis() -> Redis:
    """
    Get Redis client for dependency injection.

    In production, this should be a singleton or connection pool.
    """
    redis_client = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password if settings.redis.password else None,
        db=settings.redis.db,
        encoding="utf-8",
        decode_responses=True,
        max_connections=settings.redis.pool_size,
    )
    try:
        yield redis_client
    finally:
        await redis_client.close()


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

    In development mode, accepts mock bearer token for testing.
    """
    # Check for mock auth token in development mode
    if settings.app.app_debug:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer mock-dev-token-"):
            # Create a mock session for development
            from uuid import UUID
            mock_session = SessionData(
                user_id=UUID("00000000-0000-0000-0000-000000000001"),  # Mock user ID
                tenant_id=UUID("00000000-0000-0000-0000-000000000001"),  # Mock tenant ID
                email="dev@example.com",
                is_superuser=True,
                role="admin",
            )
            return mock_session

    session_id = request.cookies.get(settings.session.cookie_name)

    if not session_id:
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

    # Extend session if configured
    if settings.session.extend_on_activity:
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
