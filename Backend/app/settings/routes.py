"""
Settings API routes.

Provides REST endpoints for managing platform settings, SSO providers,
authentication policies, and related configurations.
"""

import uuid
from typing import Annotated, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import CurrentUserDep, ClientIpDep, UserAgentDep
from app.models.settings import (
    SettingsScopeType,
    AuthDomainType,
    SSOProviderType,
)
from app.settings.service import (
    SettingsService,
    SettingsValidationError,
    SettingsSecurityError,
)
from app.settings.sso import (
    SSOService,
    SSOError,
    SSOConfigError,
    SSOAuthError,
    get_callback_url,
    get_acs_url,
)
from app.settings.schemas import (
    AuthPolicyResponse,
    AuthPolicyUpdateRequest,
    SSOProviderResponse,
    SSOProviderListResponse,
    SSOProviderCreateRequest,
    SSOProviderUpdateRequest,
    SecurityPolicyResponse,
    SecurityPolicyUpdateRequest,
    BrandingResponse,
    BrandingUpdateRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
    ChangePasswordRequest,
    FeatureFlagResponse,
    FeatureFlagUpdateRequest,
    AuditLogResponse,
    AuditLogListResponse,
    SettingsCatalogResponse,
)


router = APIRouter(prefix="/settings", tags=["settings"])


# ===========================================
# Dependencies
# ===========================================

async def get_settings_service(
    db: AsyncSession = Depends(get_session),
) -> SettingsService:
    """Get settings service instance."""
    return SettingsService(db)


async def get_sso_service(
    db: AsyncSession = Depends(get_session),
) -> SSOService:
    """Get SSO service instance."""
    return SSOService(db)


SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
SSOServiceDep = Annotated[SSOService, Depends(get_sso_service)]


def parse_scope_type(scope_type: str) -> SettingsScopeType:
    """Parse scope type string to enum."""
    try:
        return SettingsScopeType(scope_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope_type: {scope_type}"
        )


def parse_auth_domain(domain: str) -> AuthDomainType:
    """Parse auth domain string to enum."""
    try:
        return AuthDomainType(domain)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid domain: {domain}"
        )


def parse_provider_type(provider_type: str) -> SSOProviderType:
    """Parse provider type string to enum."""
    try:
        return SSOProviderType(provider_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider_type: {provider_type}"
        )


# ===========================================
# Settings Catalog
# ===========================================

@router.get("/catalog", response_model=SettingsCatalogResponse)
async def get_settings_catalog(
    current_user: CurrentUserDep,
):
    """
    Get settings catalog.

    Returns the list of available settings with their definitions,
    types, validation rules, and permission requirements.
    """
    # Define settings categories
    categories = [
        {"key": "auth", "title": "Authentication", "title_i18n": "settings.category.auth", "order": 1},
        {"key": "security", "title": "Security", "title_i18n": "settings.category.security", "order": 2},
        {"key": "branding", "title": "Branding", "title_i18n": "settings.category.branding", "order": 3},
        {"key": "notifications", "title": "Notifications", "title_i18n": "settings.category.notifications", "order": 4},
        {"key": "advanced", "title": "Advanced", "title_i18n": "settings.category.advanced", "order": 5},
    ]

    # Define settings
    settings = [
        # Auth settings
        {
            "key": "auth.admin.email_password_enabled",
            "title": "Email & Password Login",
            "title_i18n": "settings.auth.email_password_enabled",
            "description": "Allow administrators to login with email and password",
            "category": "auth",
            "type": "boolean",
            "default": True,
            "permission_read": "settings.auth.read",
            "permission_write": "settings.auth.write",
            "ui_hints": {"widget": "toggle"},
        },
        {
            "key": "auth.admin.sso_enabled",
            "title": "Single Sign-On",
            "title_i18n": "settings.auth.sso_enabled",
            "description": "Enable SSO authentication for administrators",
            "category": "auth",
            "type": "boolean",
            "default": False,
            "permission_read": "settings.auth.read",
            "permission_write": "settings.auth.write",
            "ui_hints": {"widget": "toggle"},
        },
        {
            "key": "auth.session_timeout_days",
            "title": "Session Timeout",
            "title_i18n": "settings.auth.session_timeout",
            "description": "Number of days before sessions expire",
            "category": "auth",
            "type": "number",
            "default": 1,
            "validation": {"minimum": 1, "maximum": 365},
            "permission_read": "settings.auth.read",
            "permission_write": "settings.auth.write",
            "ui_hints": {"widget": "number", "suffix": "days"},
        },
        # Security settings
        {
            "key": "security.password_min_length",
            "title": "Minimum Password Length",
            "title_i18n": "settings.security.password_min_length",
            "category": "security",
            "type": "number",
            "default": 8,
            "validation": {"minimum": 6, "maximum": 128},
            "permission_read": "settings.security.read",
            "permission_write": "settings.security.write",
        },
        {
            "key": "security.egress_enabled",
            "title": "Allow External Connections",
            "title_i18n": "settings.security.egress_enabled",
            "description": "Allow the platform to make external network requests",
            "category": "security",
            "type": "boolean",
            "default": True,
            "permission_read": "settings.security.read",
            "permission_write": "settings.security.write",
        },
    ]

    return SettingsCatalogResponse(categories=categories, settings=settings)


# ===========================================
# Auth Policy Endpoints
# ===========================================

@router.get("/auth-policy", response_model=AuthPolicyResponse)
async def get_auth_policy(
    domain: str = Query(..., description="Auth domain: admin, members, or webapp"),
    scope_type: str = Query(default="system"),
    scope_id: Optional[str] = Query(default=None),
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
):
    """Get authentication policy for a domain."""
    domain_enum = parse_auth_domain(domain)
    scope_enum = parse_scope_type(scope_type)
    scope_uuid = uuid.UUID(scope_id) if scope_id else None

    policy = await service.get_or_create_auth_policy(domain_enum, scope_enum, scope_uuid)
    return AuthPolicyResponse(**policy.to_dict())


@router.put("/auth-policy", response_model=AuthPolicyResponse)
async def update_auth_policy(
    request: AuthPolicyUpdateRequest,
    domain: str = Query(..., description="Auth domain: admin, members, or webapp"),
    scope_type: str = Query(default="system"),
    scope_id: Optional[str] = Query(default=None),
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
    ip_address: ClientIpDep = None,
    user_agent: UserAgentDep = None,
):
    """Update authentication policy for a domain."""
    domain_enum = parse_auth_domain(domain)
    scope_enum = parse_scope_type(scope_type)
    scope_uuid = uuid.UUID(scope_id) if scope_id else None

    # Build updates dict
    updates = request.model_dump(exclude_unset=True, exclude={"confirm_risk"})

    try:
        policy = await service.update_auth_policy(
            domain=domain_enum,
            updates=updates,
            scope_type=scope_enum,
            scope_id=scope_uuid,
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=ip_address,
            user_agent=user_agent,
            confirm_risk=request.confirm_risk,
        )
        await service.db.commit()
        return AuthPolicyResponse(**policy.to_dict())
    except SettingsValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except SettingsSecurityError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# ===========================================
# SSO Provider Endpoints
# ===========================================

@router.get("/sso/providers", response_model=SSOProviderListResponse)
async def list_sso_providers(
    domain: str = Query(..., description="Auth domain: admin, members, or webapp"),
    scope_type: str = Query(default="system"),
    scope_id: Optional[str] = Query(default=None),
    enabled_only: bool = Query(default=False),
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
):
    """List SSO providers for a domain."""
    domain_enum = parse_auth_domain(domain)
    scope_enum = parse_scope_type(scope_type)
    scope_uuid = uuid.UUID(scope_id) if scope_id else None

    providers = await service.get_sso_providers(
        domain=domain_enum,
        scope_type=scope_enum,
        scope_id=scope_uuid,
        enabled_only=enabled_only,
    )

    # Add callback URLs
    provider_responses = []
    for p in providers:
        response = SSOProviderResponse(**p.to_dict())
        response.callback_url = get_callback_url(p.provider_type, str(p.id), p.domain)
        if p.provider_type == SSOProviderType.SAML:
            response.acs_url = get_acs_url(str(p.id), p.domain)
        provider_responses.append(response)

    return SSOProviderListResponse(providers=provider_responses, total=len(providers))


@router.post("/sso/providers", response_model=SSOProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_sso_provider(
    request: SSOProviderCreateRequest,
    domain: str = Query(..., description="Auth domain: admin, members, or webapp"),
    scope_type: str = Query(default="system"),
    scope_id: Optional[str] = Query(default=None),
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
    ip_address: ClientIpDep = None,
    user_agent: UserAgentDep = None,
):
    """Create a new SSO provider."""
    domain_enum = parse_auth_domain(domain)
    scope_enum = parse_scope_type(scope_type)
    scope_uuid = uuid.UUID(scope_id) if scope_id else None
    provider_type = parse_provider_type(request.provider_type)

    try:
        provider = await service.create_sso_provider(
            domain=domain_enum,
            provider_type=provider_type,
            name=request.name,
            config=request.config,
            secrets=request.secrets,
            scope_type=scope_enum,
            scope_id=scope_uuid,
            display_name=request.display_name,
            icon=request.icon,
            enabled=request.enabled,
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await service.db.commit()

        response = SSOProviderResponse(**provider.to_dict())
        response.callback_url = get_callback_url(provider.provider_type, str(provider.id), provider.domain)
        if provider.provider_type == SSOProviderType.SAML:
            response.acs_url = get_acs_url(str(provider.id), provider.domain)
        return response
    except SettingsValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sso/providers/{provider_id}", response_model=SSOProviderResponse)
async def get_sso_provider(
    provider_id: uuid.UUID,
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
):
    """Get a specific SSO provider."""
    provider = await service.get_sso_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSO provider not found")

    response = SSOProviderResponse(**provider.to_dict())
    response.callback_url = get_callback_url(provider.provider_type, str(provider.id), provider.domain)
    if provider.provider_type == SSOProviderType.SAML:
        response.acs_url = get_acs_url(str(provider.id), provider.domain)
    return response


@router.put("/sso/providers/{provider_id}", response_model=SSOProviderResponse)
async def update_sso_provider(
    provider_id: uuid.UUID,
    request: SSOProviderUpdateRequest,
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
    ip_address: ClientIpDep = None,
    user_agent: UserAgentDep = None,
):
    """Update an SSO provider."""
    updates = request.model_dump(exclude_unset=True, exclude={"secrets"})

    try:
        provider = await service.update_sso_provider(
            provider_id=provider_id,
            updates=updates,
            secrets=request.secrets,
            actor_id=current_user.id,
            actor_email=current_user.email,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await service.db.commit()

        response = SSOProviderResponse(**provider.to_dict())
        response.callback_url = get_callback_url(provider.provider_type, str(provider.id), provider.domain)
        if provider.provider_type == SSOProviderType.SAML:
            response.acs_url = get_acs_url(str(provider.id), provider.domain)
        return response
    except SettingsValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/sso/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sso_provider(
    provider_id: uuid.UUID,
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
    ip_address: ClientIpDep = None,
    user_agent: UserAgentDep = None,
):
    """Delete an SSO provider."""
    deleted = await service.delete_sso_provider(
        provider_id=provider_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSO provider not found")
    await service.db.commit()


# ===========================================
# Security Policy Endpoints
# ===========================================

@router.get("/security", response_model=SecurityPolicyResponse)
async def get_security_policy(
    scope_type: str = Query(default="system"),
    scope_id: Optional[str] = Query(default=None),
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
):
    """Get security policy."""
    scope_enum = parse_scope_type(scope_type)
    scope_uuid = uuid.UUID(scope_id) if scope_id else None

    policy = await service.get_or_create_security_policy(scope_enum, scope_uuid)
    return SecurityPolicyResponse(**policy.to_dict())


@router.put("/security", response_model=SecurityPolicyResponse)
async def update_security_policy(
    request: SecurityPolicyUpdateRequest,
    scope_type: str = Query(default="system"),
    scope_id: Optional[str] = Query(default=None),
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
    ip_address: ClientIpDep = None,
    user_agent: UserAgentDep = None,
):
    """Update security policy."""
    scope_enum = parse_scope_type(scope_type)
    scope_uuid = uuid.UUID(scope_id) if scope_id else None

    updates = request.model_dump(exclude_unset=True)

    policy = await service.update_security_policy(
        updates=updates,
        scope_type=scope_enum,
        scope_id=scope_uuid,
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await service.db.commit()
    return SecurityPolicyResponse(**policy.to_dict())


# ===========================================
# Branding Endpoints
# ===========================================

@router.get("/branding", response_model=BrandingResponse)
async def get_branding(
    scope_type: str = Query(default="system"),
    scope_id: Optional[str] = Query(default=None),
    service: SettingsServiceDep = None,
):
    """Get branding settings. Public endpoint."""
    scope_enum = parse_scope_type(scope_type)
    scope_uuid = uuid.UUID(scope_id) if scope_id else None

    branding = await service.get_or_create_branding(scope_enum, scope_uuid)

    response_data = branding.to_dict()
    # TODO: Generate signed URLs for logo, favicon, background
    response_data["logo_url"] = None
    response_data["favicon_url"] = None
    response_data["login_background_url"] = None

    return BrandingResponse(**response_data)


@router.put("/branding", response_model=BrandingResponse)
async def update_branding(
    request: BrandingUpdateRequest,
    scope_type: str = Query(default="system"),
    scope_id: Optional[str] = Query(default=None),
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
    ip_address: ClientIpDep = None,
    user_agent: UserAgentDep = None,
):
    """Update branding settings."""
    scope_enum = parse_scope_type(scope_type)
    scope_uuid = uuid.UUID(scope_id) if scope_id else None

    updates = request.model_dump(exclude_unset=True)

    branding = await service.update_branding(
        updates=updates,
        scope_type=scope_enum,
        scope_id=scope_uuid,
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await service.db.commit()

    response_data = branding.to_dict()
    response_data["logo_url"] = None
    response_data["favicon_url"] = None
    response_data["login_background_url"] = None

    return BrandingResponse(**response_data)


# ===========================================
# Profile Endpoints
# ===========================================

@router.get("/profile/me", response_model=UserProfileResponse)
async def get_my_profile(
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
):
    """Get current user's profile."""
    profile = await service.get_or_create_user_profile(current_user.id)

    response_data = profile.to_dict()
    # TODO: Generate signed URL for avatar
    response_data["avatar_url"] = None

    return UserProfileResponse(**response_data)


@router.patch("/profile/me", response_model=UserProfileResponse)
async def update_my_profile(
    request: UserProfileUpdateRequest,
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
    ip_address: ClientIpDep = None,
    user_agent: UserAgentDep = None,
):
    """Update current user's profile."""
    updates = request.model_dump(exclude_unset=True)

    profile = await service.update_user_profile(
        user_id=current_user.id,
        updates=updates,
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await service.db.commit()

    response_data = profile.to_dict()
    response_data["avatar_url"] = None

    return UserProfileResponse(**response_data)


# ===========================================
# Feature Flag Endpoints
# ===========================================

@router.get("/features/{flag_key}", response_model=FeatureFlagResponse)
async def get_feature_flag(
    flag_key: str,
    scope_type: str = Query(default="system"),
    scope_id: Optional[str] = Query(default=None),
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
):
    """Get a feature flag."""
    scope_enum = parse_scope_type(scope_type)
    scope_uuid = uuid.UUID(scope_id) if scope_id else None

    enabled = await service.get_feature_flag(flag_key, scope_enum, scope_uuid)

    return FeatureFlagResponse(
        id="",
        scope_type=scope_type,
        scope_id=scope_id,
        flag_key=flag_key,
        enabled=enabled,
    )


@router.put("/features/{flag_key}", response_model=FeatureFlagResponse)
async def set_feature_flag(
    flag_key: str,
    request: FeatureFlagUpdateRequest,
    scope_type: str = Query(default="system"),
    scope_id: Optional[str] = Query(default=None),
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
    ip_address: ClientIpDep = None,
    user_agent: UserAgentDep = None,
):
    """Set a feature flag."""
    scope_enum = parse_scope_type(scope_type)
    scope_uuid = uuid.UUID(scope_id) if scope_id else None

    flag = await service.set_feature_flag(
        flag_key=flag_key,
        enabled=request.enabled,
        scope_type=scope_enum,
        scope_id=scope_uuid,
        description=request.description,
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await service.db.commit()

    return FeatureFlagResponse(**flag.to_dict())


# ===========================================
# Audit Log Endpoints
# ===========================================

@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    scope_type: Optional[str] = Query(default=None),
    scope_id: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: SettingsServiceDep = None,
    current_user: CurrentUserDep = None,
):
    """List settings audit logs."""
    scope_enum = parse_scope_type(scope_type) if scope_type else None
    scope_uuid = uuid.UUID(scope_id) if scope_id else None

    logs = await service.get_audit_logs(
        scope_type=scope_enum,
        scope_id=scope_uuid,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )

    return AuditLogListResponse(
        logs=[AuditLogResponse(**log.to_dict()) for log in logs],
        total=len(logs),
    )
