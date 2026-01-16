"""
SSO authentication routes.

Handles the actual SSO login flows for OIDC, OAuth2, and SAML.
Separate from the settings management routes.
"""

import uuid
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.config import settings as app_settings
from app.core.session import SessionManager
from app.models.settings import AuthDomainType, SSOProviderType
from app.settings.sso import (
    SSOService,
    SSOError,
    SSOConfigError,
    SSOAuthError,
    SSOStateError,
    SSOUserInfo,
)
from app.settings.service import SettingsService


router = APIRouter(prefix="/sso", tags=["sso-auth"])


# ===========================================
# Dependencies
# ===========================================

async def get_sso_service(db: AsyncSession = Depends(get_session)) -> SSOService:
    return SSOService(db)


async def get_settings_service(db: AsyncSession = Depends(get_session)) -> SettingsService:
    return SettingsService(db)


def get_session_manager() -> SessionManager:
    """Get session manager instance."""
    from app.core.redis import get_redis_pool
    import asyncio
    # Note: In production, this should be properly injected
    return SessionManager(asyncio.get_event_loop().run_until_complete(get_redis_pool()))


# ===========================================
# Login Initiation Routes
# ===========================================

@router.get("/{domain}/{provider_type}/{provider_id}/login")
async def initiate_sso_login(
    domain: str,
    provider_type: str,
    provider_id: uuid.UUID,
    redirect_uri: Optional[str] = Query(default=None, description="URI to redirect after login"),
    sso_service: SSOService = Depends(get_sso_service),
):
    """
    Initiate SSO login flow.

    Redirects the user to the identity provider for authentication.
    """
    try:
        # Validate domain
        try:
            domain_enum = AuthDomainType(domain)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid domain: {domain}"
            )

        # Get authorization URL
        auth_url = await sso_service.initiate_sso(
            provider_id=provider_id,
            redirect_uri=redirect_uri,
        )

        await sso_service.db.commit()

        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)

    except SSOConfigError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSO configuration error: {str(e)}"
        )
    except SSOError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ===========================================
# Callback Routes
# ===========================================

@router.get("/{domain}/oidc/{provider_id}/callback")
@router.get("/{domain}/oauth2/{provider_id}/callback")
async def handle_oauth_callback(
    request: Request,
    domain: str,
    provider_id: uuid.UUID,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
    sso_service: SSOService = Depends(get_sso_service),
    settings_service: SettingsService = Depends(get_settings_service),
    db: AsyncSession = Depends(get_session),
):
    """
    Handle OIDC/OAuth2 callback from identity provider.

    Validates the response, creates/updates user, and establishes session.
    """
    frontend_base = app_settings.app.frontend_base_url.rstrip("/")
    error_redirect = f"{frontend_base}/auth/login"
    success_redirect = app_settings.app.sso_success_redirect_path

    try:
        # Validate domain
        try:
            domain_enum = AuthDomainType(domain)
        except ValueError:
            return RedirectResponse(
                url=f"{error_redirect}?error=invalid_domain",
                status_code=status.HTTP_302_FOUND
            )

        # Complete SSO flow
        user_info = await sso_service.complete_sso(
            provider_id=provider_id,
            code=code,
            state=state,
            error=error,
            error_description=error_description,
        )

        await db.commit()

        # Process user info and create session
        response = await _process_sso_user(
            user_info=user_info,
            domain=domain_enum,
            settings_service=settings_service,
            db=db,
            success_redirect=success_redirect,
            error_redirect=error_redirect,
        )

        return response

    except SSOStateError as e:
        return RedirectResponse(
            url=f"{error_redirect}?error=invalid_state&message={str(e)}",
            status_code=status.HTTP_302_FOUND
        )
    except SSOAuthError as e:
        return RedirectResponse(
            url=f"{error_redirect}?error=auth_failed&message={str(e)}",
            status_code=status.HTTP_302_FOUND
        )
    except SSOConfigError as e:
        return RedirectResponse(
            url=f"{error_redirect}?error=config_error&message={str(e)}",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{error_redirect}?error=unknown&message=Authentication+failed",
            status_code=status.HTTP_302_FOUND
        )


@router.post("/{domain}/saml/{provider_id}/acs")
async def handle_saml_acs(
    request: Request,
    domain: str,
    provider_id: uuid.UUID,
    sso_service: SSOService = Depends(get_sso_service),
    settings_service: SettingsService = Depends(get_settings_service),
    db: AsyncSession = Depends(get_session),
):
    """
    Handle SAML Assertion Consumer Service (ACS) POST.

    Receives and validates SAML Response from identity provider.
    """
    frontend_base = app_settings.app.frontend_base_url.rstrip("/")
    error_redirect = f"{frontend_base}/auth/login"
    success_redirect = app_settings.app.sso_success_redirect_path

    try:
        # Validate domain
        try:
            domain_enum = AuthDomainType(domain)
        except ValueError:
            return RedirectResponse(
                url=f"{error_redirect}?error=invalid_domain",
                status_code=status.HTTP_302_FOUND
            )

        # Parse form data
        form_data = await request.form()
        saml_response = form_data.get("SAMLResponse")
        relay_state = form_data.get("RelayState")

        # Complete SSO flow
        user_info = await sso_service.complete_sso(
            provider_id=provider_id,
            SAMLResponse=saml_response,
            RelayState=relay_state,
        )

        await db.commit()

        # Process user info and create session
        response = await _process_sso_user(
            user_info=user_info,
            domain=domain_enum,
            settings_service=settings_service,
            db=db,
            success_redirect=success_redirect,
            error_redirect=error_redirect,
        )

        return response

    except SSOStateError as e:
        return RedirectResponse(
            url=f"{error_redirect}?error=invalid_state",
            status_code=status.HTTP_302_FOUND
        )
    except SSOAuthError as e:
        return RedirectResponse(
            url=f"{error_redirect}?error=auth_failed",
            status_code=status.HTTP_302_FOUND
        )
    except NotImplementedError as e:
        return RedirectResponse(
            url=f"{error_redirect}?error=not_implemented&message=SAML+not+fully+implemented",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{error_redirect}?error=unknown",
            status_code=status.HTTP_302_FOUND
        )


# ===========================================
# Helper Functions
# ===========================================

async def _process_sso_user(
    user_info: SSOUserInfo,
    domain: AuthDomainType,
    settings_service: SettingsService,
    db: AsyncSession,
    success_redirect: str,
    error_redirect: str,
) -> Response:
    """
    Process SSO user info and create session.

    This function:
    1. Checks if user exists by SSO provider ID or email
    2. Creates user if needed (based on policy)
    3. Creates session and sets cookie
    4. Redirects to success page
    """
    from app.models.user import User
    from sqlalchemy import select, or_

    # Get auth policy for auto-create settings
    auth_policy = await settings_service.get_auth_policy(domain)

    # Look for existing user
    query = select(User).where(
        or_(
            User.sso_provider_id == user_info.external_id,
            User.email == user_info.email,
        )
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        # Check if we should auto-create
        should_create = False

        if domain == AuthDomainType.ADMIN and auth_policy and auth_policy.auto_create_admin_on_first_sso:
            # Check email domain restriction
            if auth_policy.auto_create_admin_email_domains and user_info.email:
                email_domain = user_info.email.split("@")[-1].lower()
                allowed_domains = [d.lower() for d in auth_policy.auto_create_admin_email_domains]
                if email_domain in allowed_domains:
                    should_create = True
        elif domain == AuthDomainType.MEMBERS and auth_policy and auth_policy.self_signup_enabled:
            # Check email domain restriction for members
            if auth_policy.allowed_email_domains and user_info.email:
                email_domain = user_info.email.split("@")[-1].lower()
                allowed_domains = [d.lower() for d in auth_policy.allowed_email_domains]
                if email_domain in allowed_domains:
                    should_create = True
            elif not auth_policy.allowed_email_domains:
                should_create = True

        if not should_create:
            return RedirectResponse(
                url=f"{error_redirect}?error=user_not_found&message=User+not+found+and+auto-creation+disabled",
                status_code=status.HTTP_302_FOUND
            )

        # Create new user
        user = User(
            email=user_info.email,
            name=user_info.name or user_info.email.split("@")[0],
            password_hash="",  # SSO users don't have password
            is_active=True,
            is_verified=user_info.email_verified,
            sso_provider=f"{user_info.provider_type.value}:{user_info.provider_id}",
            sso_provider_id=user_info.external_id,
        )
        db.add(user)
        await db.flush()

    else:
        # Update SSO info if needed
        if not user.sso_provider_id:
            user.sso_provider = f"{user_info.provider_type.value}:{user_info.provider_id}"
            user.sso_provider_id = user_info.external_id

    # Update last login
    from datetime import datetime, timezone
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Create session
    # Note: In production, use the actual SessionManager from dependencies
    from app.core.session import SessionData
    import secrets

    session_id = secrets.token_urlsafe(32)
    session_data = SessionData(
        user_id=str(user.id),
        email=user.email,
        name=user.name,
        ip_address="",  # Would be extracted from request
        user_agent="",
    )

    # TODO: Store session in Redis
    # session_manager = get_session_manager()
    # await session_manager.create(session_id, session_data)

    # Build redirect response with session cookie
    frontend_base = app_settings.app.frontend_base_url.rstrip("/")
    redirect_url = f"{frontend_base}{success_redirect}"

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

    # Set session cookie
    response.set_cookie(
        key=app_settings.session.cookie_name,
        value=session_id,
        max_age=app_settings.session.ttl,
        httponly=app_settings.session.cookie_httponly,
        secure=app_settings.session.cookie_secure,
        samesite=app_settings.session.cookie_samesite,
        domain=app_settings.session.cookie_domain or None,
    )

    return response


# ===========================================
# Public Provider List (for login page)
# ===========================================

@router.get("/{domain}/providers")
async def get_public_sso_providers(
    domain: str,
    sso_service: SSOService = Depends(get_sso_service),
):
    """
    Get enabled SSO providers for login page.

    Returns only public information needed to render SSO login buttons.
    This endpoint is public (no auth required).
    """
    try:
        domain_enum = AuthDomainType(domain)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid domain: {domain}"
        )

    providers = await sso_service.get_enabled_providers(domain_enum)

    return {
        "providers": [
            {
                "id": str(p.id),
                "name": p.name,
                "display_name": p.display_name or p.name,
                "icon": p.icon,
                "provider_type": p.provider_type.value,
                "login_url": f"/api/v1/sso/{domain}/{p.provider_type.value}/{p.id}/login",
            }
            for p in providers
        ]
    }
