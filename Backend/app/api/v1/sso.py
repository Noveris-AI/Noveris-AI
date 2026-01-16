"""
SSO (Single Sign-On) API endpoints.

Handles SSO authentication flows for OIDC, OAuth2, and SAML providers.
"""

from __future__ import annotations

from typing import Annotated, Optional
from urllib.parse import urlencode, parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.v1.auth import get_auth_service, get_redis
from app.core.config import settings
from app.core.dependencies import get_session_manager
from app.core.session import SessionManager
from app.core.dependencies import get_client_ip, get_user_agent
from app.sso.config import sso_config
from app.sso.oauth2 import OAuth2Service
from app.sso.oidc import OIDCService
from app.schemas.auth import AuthResponse, LoginResponse, UserResponse

router = APIRouter(prefix="/auth/sso", tags=["SSO"])


# ============================================================================
# Helper Functions
# ============================================================================

def get_callback_url(request: Request, provider_id: str) -> str:
    """Get the callback URL for SSO redirect."""
    base_url = f"{request.url.scheme}://{request.headers.get('host', 'localhost')}"
    return f"{base_url}/api/v1/auth/sso/callback/{provider_id}"


async def store_state(
    redis,
    state: str,
    provider_id: str,
    redirect_to: Optional[str] = None,
) -> None:
    """Store state parameter for CSRF protection."""
    key = f"sso:state:{state}"
    await redis.setex(
        key,
        600,  # 10 minutes
        urlencode({"provider": provider_id, "redirect": redirect_to or ""}),
    )


async def verify_state(
    redis,
    state: str,
) -> Optional[dict]:
    """Verify and consume state parameter."""
    key = f"sso:state:{state}"
    data = await redis.get(key)
    if data:
        await redis.delete(key)
        # Parse stored data
        parsed = parse_qs(data)
        return {
            "provider": parsed.get("provider", [None])[0],
            "redirect": parsed.get("redirect", [None])[0],
        }
    return None


# ============================================================================
# Provider Discovery
# ============================================================================


@router.get("/providers")
async def list_providers():
    """
    List all available SSO providers.

    Returns enabled OIDC, OAuth2, and SAML providers.
    """
    return {
        "success": True,
        "data": {
            "providers": sso_config.enabled_providers,
        },
    }


# ============================================================================
# OIDC/OAuth2 Login
# ============================================================================


@router.get("/login/{provider_id}")
async def sso_login(
    provider_id: str,
    request: Request,
    redis: Annotated[object, Depends(get_redis)],
    redirect_to: Optional[str] = Query(None),
):
    """
    Initiate SSO login flow.

    Redirects user to the SSO provider's authorization page.
    Supports both OIDC and OAuth2 providers.
    """
    # Get provider configuration
    provider = sso_config.get_oidc_provider(provider_id)
    if not provider:
        provider = sso_config.get_oauth2_provider(provider_id)

    if not provider or not provider.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SSO provider '{provider_id}' not found or disabled",
        )

    # Generate state parameter
    if hasattr(provider, "generate_state"):
        state = provider.generate_state()
    else:
        import secrets
        state = secrets.token_urlsafe(32)

    # Store state
    await store_state(redis, state, provider_id, redirect_to)

    # Build authorization URL
    callback_url = get_callback_url(request, provider_id)

    if hasattr(provider, "get_authorization_url"):
        # OIDC
        nonce = provider.generate_nonce() if hasattr(provider, "generate_nonce") else None
        auth_url = provider.get_authorization_url(callback_url, state, nonce)
    else:
        # OAuth2
        auth_url = provider.get_authorization_url(callback_url, state)

    # Redirect to provider
    from fastapi.responses import RedirectResponse
    return RedirectResponse(auth_url)


# ============================================================================
# SSO Callback
# ============================================================================


@router.get("/callback/{provider_id}")
async def sso_callback(
    provider_id: str,
    request: Request,
    response: Response,
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    auth_service=Depends(get_auth_service),
    redis=Depends(get_redis),
    session_manager=Depends(get_session_manager),
    client_ip=Depends(get_client_ip),
    user_agent=Depends(get_user_agent),
):
    """
    Handle SSO callback from provider.

    Completes the authentication flow and creates a user session.
    """
    # Check for errors
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSO error: {error_description or error}",
        )

    # Verify state
    state_data = await verify_state(redis, state)
    if not state_data or state_data["provider"] != provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        )

    # Get provider configuration
    provider = sso_config.get_oidc_provider(provider_id)
    oauth2_provider = None
    if not provider:
        oauth2_provider = sso_config.get_oauth2_provider(provider_id)
        if not oauth2_provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SSO provider '{provider_id}' not found",
            )

    # Get callback URL
    callback_url = get_callback_url(request, provider_id)

    # Complete authentication flow
    try:
        if provider:
            service = OIDCService(provider)
            user_info = await service.authenticate(code, callback_url)
        else:
            service = OAuth2Service(oauth2_provider)
            user_info = await service.authenticate(code, callback_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}",
        )

    # Get or create user
    user, is_new = await auth_service.get_or_create_sso_user(
        provider=provider_id,
        provider_id=user_info["provider_user_id"],
        email=user_info["email"],
        name=user_info["name"],
    )

    # Update last login
    await auth_service.update_last_login(
        user=user,
        success=True,
        ip_address=client_ip,
        user_agent=user_agent,
        sso_provider=provider_id,
    )

    # Create session
    session_id = await session_manager.create(
        user_id=str(user.id),
        email=user.email,
        name=user.name,
        ip_address=client_ip,
        user_agent=user_agent,
        remember_me=True,  # SSO sessions are typically long-lived
    )

    # Set session cookie
    response.set_cookie(
        key=settings.session.cookie_name,
        value=session_id,
        httponly=settings.session.cookie_httponly,
        secure=settings.session.cookie_secure,
        samesite=settings.session.cookie_samesite,
        max_age=settings.session.remember_ttl,
        path="/",
        domain=settings.session.cookie_domain or None,
    )

    # Redirect to frontend
    redirect_url = state_data["redirect"] or settings.sso_success_redirect_path
    frontend_url = f"{settings.frontend_base_url}{redirect_url}"

    from fastapi.responses import RedirectResponse
    return RedirectResponse(frontend_url, status_code=302)


# ============================================================================
# SAML (placeholder for future implementation)
# ============================================================================


@router.get("/saml/login/{provider_id}")
async def saml_login(
    provider_id: str,
):
    """
    Initiate SAML SSO login flow.

    Note: This endpoint requires additional SAML library setup.
    """
    provider = sso_config.get_saml_provider(provider_id)

    if not provider or not provider.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SAML provider '{provider_id}' not found or disabled",
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="SAML SSO is not yet implemented",
    )


@router.post("/saml/acs/{provider_id}")
async def saml_acs(
    provider_id: str,
    request: Request,
):
    """
    SAML Assertion Consumer Service (ACS) endpoint.

    Handles SAML response from IdP.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="SAML SSO is not yet implemented",
    )


@router.get("/saml/metadata/{provider_id}")
async def saml_metadata(
    provider_id: str,
):
    """
    SAML metadata endpoint.

    Returns service provider metadata for the IdP.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="SAML SSO is not yet implemented",
    )
