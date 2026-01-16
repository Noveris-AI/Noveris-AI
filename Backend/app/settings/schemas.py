"""
Settings API schemas.

Pydantic models for request/response validation.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ===========================================
# Base Schemas
# ===========================================

class ScopeSchema(BaseModel):
    """Base schema for scoped resources."""
    scope_type: str = Field(default="system", description="Scope type: system, tenant, or user")
    scope_id: Optional[str] = Field(default=None, description="Scope ID (null for system)")


# ===========================================
# Settings KV
# ===========================================

class SettingValueRequest(BaseModel):
    """Request to set a setting value."""
    key: str = Field(..., description="Setting key")
    value: Any = Field(..., description="Setting value")


class SettingValueResponse(BaseModel):
    """Response for a setting value."""
    key: str
    value: Any
    scope_type: str
    scope_id: Optional[str] = None
    is_encrypted: bool = False
    version: int = 1
    updated_at: Optional[datetime] = None


class SettingsBatchUpdateRequest(BaseModel):
    """Request to update multiple settings."""
    settings: List[SettingValueRequest] = Field(..., description="Settings to update")


# ===========================================
# Auth Policy
# ===========================================

class AuthPolicyResponse(BaseModel):
    """Authentication policy response."""
    id: str
    domain: str
    scope_type: str
    scope_id: Optional[str] = None
    email_password_enabled: bool = True
    email_code_enabled: bool = False
    sso_enabled: bool = False
    session_timeout_days: int = 1
    auto_create_admin_on_first_sso: bool = False
    auto_create_admin_email_domains: Optional[List[str]] = None
    self_signup_enabled: bool = False
    signup_auto_create_personal_space: bool = False
    allowed_email_domains: Optional[List[str]] = None
    updated_at: Optional[datetime] = None


class AuthPolicyUpdateRequest(BaseModel):
    """Request to update auth policy."""
    email_password_enabled: Optional[bool] = None
    email_code_enabled: Optional[bool] = None
    sso_enabled: Optional[bool] = None
    session_timeout_days: Optional[int] = Field(default=None, ge=1, le=365)
    auto_create_admin_on_first_sso: Optional[bool] = None
    auto_create_admin_email_domains: Optional[List[str]] = None
    self_signup_enabled: Optional[bool] = None
    signup_auto_create_personal_space: Optional[bool] = None
    allowed_email_domains: Optional[List[str]] = None
    confirm_risk: bool = Field(default=False, description="Confirm risky operations")


# ===========================================
# SSO Provider
# ===========================================

class SSOProviderConfigOIDC(BaseModel):
    """OIDC provider configuration."""
    issuer_or_discovery_url: str = Field(..., description="OIDC issuer URL or discovery document URL")
    client_id: str = Field(..., description="OAuth client ID")
    scopes: str = Field(default="openid profile email", description="OAuth scopes")
    use_pkce: bool = Field(default=True, description="Use PKCE for enhanced security")
    claim_mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description="Claim mapping: {email: 'email', name: 'name', groups: 'groups'}"
    )


class SSOProviderConfigOAuth2(BaseModel):
    """OAuth2 provider configuration."""
    authorization_endpoint: str = Field(..., description="Authorization endpoint URL")
    token_endpoint: str = Field(..., description="Token endpoint URL")
    userinfo_endpoint: str = Field(..., description="UserInfo endpoint URL")
    client_id: str = Field(..., description="OAuth client ID")
    scopes: str = Field(default="", description="OAuth scopes")
    use_pkce: bool = Field(default=False, description="Use PKCE")
    claim_mapping: Optional[Dict[str, str]] = Field(default=None, description="Claim mapping")


class SSOProviderConfigSAML(BaseModel):
    """SAML provider configuration."""
    idp_sso_url: str = Field(..., description="IdP SSO URL")
    idp_entity_id: Optional[str] = Field(default=None, description="IdP Entity ID")
    sp_entity_id: Optional[str] = Field(default=None, description="SP Entity ID (auto-generated if not set)")
    nameid_format: Optional[str] = Field(default=None, description="NameID format")
    attribute_mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description="Attribute mapping: {email: 'mail', name: 'displayName'}"
    )


class SSOProviderSecretsOIDC(BaseModel):
    """OIDC provider secrets."""
    client_secret: Optional[str] = Field(default=None, description="OAuth client secret")


class SSOProviderSecretsOAuth2(BaseModel):
    """OAuth2 provider secrets."""
    client_secret: Optional[str] = Field(default=None, description="OAuth client secret")


class SSOProviderSecretsSAML(BaseModel):
    """SAML provider secrets."""
    x509_cert_pem: str = Field(..., description="X509 signing certificate (PEM format)")


class SSOProviderCreateRequest(BaseModel):
    """Request to create SSO provider."""
    provider_type: str = Field(..., description="Provider type: oidc, oauth2, or saml")
    name: str = Field(..., min_length=1, max_length=100, description="Provider name")
    display_name: Optional[str] = Field(default=None, max_length=100)
    icon: Optional[str] = Field(default=None, max_length=50)
    enabled: bool = Field(default=False)
    config: Dict[str, Any] = Field(..., description="Provider configuration")
    secrets: Optional[Dict[str, Any]] = Field(default=None, description="Provider secrets")


class SSOProviderUpdateRequest(BaseModel):
    """Request to update SSO provider."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=100)
    icon: Optional[str] = Field(default=None, max_length=50)
    enabled: Optional[bool] = None
    order: Optional[int] = Field(default=None, ge=0)
    config: Optional[Dict[str, Any]] = Field(default=None, description="Provider configuration updates")
    secrets: Optional[Dict[str, Any]] = Field(default=None, description="Provider secrets updates")


class SSOProviderResponse(BaseModel):
    """SSO provider response."""
    id: str
    scope_type: str
    scope_id: Optional[str] = None
    domain: str
    provider_type: str
    name: str
    display_name: Optional[str] = None
    icon: Optional[str] = None
    enabled: bool
    order: int
    config: Optional[Dict[str, Any]] = None
    # Note: secrets are never returned
    callback_url: Optional[str] = None  # Generated callback URL
    acs_url: Optional[str] = None  # For SAML
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SSOProviderListResponse(BaseModel):
    """List of SSO providers."""
    providers: List[SSOProviderResponse]
    total: int


# ===========================================
# Security Policy
# ===========================================

class SecurityPolicyResponse(BaseModel):
    """Security policy response."""
    id: str
    scope_type: str
    scope_id: Optional[str] = None
    session_idle_timeout_minutes: int = 30
    session_absolute_timeout_days: int = 7
    max_concurrent_sessions: int = 5
    force_logout_on_password_change: bool = True
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_digit: bool = True
    password_require_special: bool = True
    password_history_count: int = 5
    password_expiry_days: Optional[int] = None
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    ip_allowlist: Optional[List[str]] = None
    ip_denylist: Optional[List[str]] = None
    ip_access_control_enabled: bool = False
    audit_log_enabled: bool = True
    audit_log_retention_days: int = 90
    egress_enabled: bool = True
    egress_allowed_domains: Optional[List[str]] = None
    updated_at: Optional[datetime] = None


class SecurityPolicyUpdateRequest(BaseModel):
    """Request to update security policy."""
    session_idle_timeout_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    session_absolute_timeout_days: Optional[int] = Field(default=None, ge=1, le=365)
    max_concurrent_sessions: Optional[int] = Field(default=None, ge=1, le=100)
    force_logout_on_password_change: Optional[bool] = None
    password_min_length: Optional[int] = Field(default=None, ge=6, le=128)
    password_require_uppercase: Optional[bool] = None
    password_require_lowercase: Optional[bool] = None
    password_require_digit: Optional[bool] = None
    password_require_special: Optional[bool] = None
    password_history_count: Optional[int] = Field(default=None, ge=0, le=24)
    password_expiry_days: Optional[int] = Field(default=None, ge=0, le=365)
    max_login_attempts: Optional[int] = Field(default=None, ge=1, le=20)
    lockout_duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    ip_allowlist: Optional[List[str]] = None
    ip_denylist: Optional[List[str]] = None
    ip_access_control_enabled: Optional[bool] = None
    audit_log_enabled: Optional[bool] = None
    audit_log_retention_days: Optional[int] = Field(default=None, ge=7, le=730)
    egress_enabled: Optional[bool] = None
    egress_allowed_domains: Optional[List[str]] = None


# ===========================================
# Branding
# ===========================================

class BrandingResponse(BaseModel):
    """Branding settings response."""
    id: str
    scope_type: str
    scope_id: Optional[str] = None
    brand_name: Optional[str] = None
    logo_url: Optional[str] = None  # Signed URL
    favicon_url: Optional[str] = None  # Signed URL
    login_page_title: Optional[str] = None
    dashboard_title: Optional[str] = None
    browser_title_template: Optional[str] = None
    login_background_url: Optional[str] = None  # Signed URL
    primary_color: Optional[str] = None
    color_scheme_locked: bool = True
    updated_at: Optional[datetime] = None


class BrandingUpdateRequest(BaseModel):
    """Request to update branding."""
    brand_name: Optional[str] = Field(default=None, max_length=100)
    login_page_title: Optional[str] = Field(default=None, max_length=200)
    dashboard_title: Optional[str] = Field(default=None, max_length=200)
    browser_title_template: Optional[str] = Field(default=None, max_length=200)
    primary_color: Optional[str] = Field(default=None, max_length=20)


# ===========================================
# User Profile
# ===========================================

class UserProfileResponse(BaseModel):
    """User profile response."""
    user_id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None  # Signed URL
    locale: str = "zh-CN"
    timezone: str = "Asia/Shanghai"
    preferences: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None


class UserProfileUpdateRequest(BaseModel):
    """Request to update user profile."""
    display_name: Optional[str] = Field(default=None, max_length=100)
    locale: Optional[str] = Field(default=None, max_length=10)
    timezone: Optional[str] = Field(default=None, max_length=50)
    preferences: Optional[Dict[str, Any]] = None


class ChangePasswordRequest(BaseModel):
    """Request to change password."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


# ===========================================
# Notification Channel
# ===========================================

class NotificationChannelResponse(BaseModel):
    """Notification channel response."""
    id: str
    scope_type: str
    scope_id: Optional[str] = None
    channel_type: str
    name: str
    enabled: bool
    config: Optional[Dict[str, Any]] = None
    last_test_at: Optional[datetime] = None
    last_test_success: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NotificationChannelCreateRequest(BaseModel):
    """Request to create notification channel."""
    channel_type: str = Field(..., description="Channel type: smtp, webhook, slack, feishu, wecom, dingtalk")
    name: str = Field(..., min_length=1, max_length=100)
    enabled: bool = Field(default=False)
    config: Dict[str, Any] = Field(..., description="Channel configuration")
    secrets: Optional[Dict[str, Any]] = Field(default=None, description="Channel secrets")


class NotificationChannelUpdateRequest(BaseModel):
    """Request to update notification channel."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    secrets: Optional[Dict[str, Any]] = None


# ===========================================
# Feature Flag
# ===========================================

class FeatureFlagResponse(BaseModel):
    """Feature flag response."""
    id: str
    scope_type: str
    scope_id: Optional[str] = None
    flag_key: str
    enabled: bool
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None


class FeatureFlagUpdateRequest(BaseModel):
    """Request to update feature flag."""
    enabled: bool = Field(..., description="Enable or disable the flag")
    description: Optional[str] = Field(default=None, max_length=500)


# ===========================================
# Audit Log
# ===========================================

class AuditLogResponse(BaseModel):
    """Audit log entry response."""
    id: str
    scope_type: str
    scope_id: Optional[str] = None
    actor_id: str
    actor_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    resource_key: Optional[str] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """List of audit logs."""
    logs: List[AuditLogResponse]
    total: int


# ===========================================
# Settings Catalog
# ===========================================

class SettingDefinition(BaseModel):
    """Definition of a setting for the catalog."""
    key: str
    title: str
    title_i18n: Optional[str] = None
    description: Optional[str] = None
    description_i18n: Optional[str] = None
    category: str
    type: str  # string, boolean, number, json, select, multiselect
    default: Any = None
    options: Optional[List[Dict[str, Any]]] = None  # For select/multiselect
    validation: Optional[Dict[str, Any]] = None  # JSON Schema for validation
    sensitive: bool = False
    permission_read: str
    permission_write: str
    ui_hints: Optional[Dict[str, Any]] = None  # UI rendering hints


class SettingsCatalogResponse(BaseModel):
    """Settings catalog response."""
    categories: List[Dict[str, Any]]
    settings: List[SettingDefinition]
