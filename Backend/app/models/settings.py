"""
Settings database models.

Implements a flexible settings system with support for:
- System-wide settings
- Tenant/workspace settings
- User-level settings
- SSO provider configuration
- Security policies
- Notification channels
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


UTC = timezone.utc


class SettingsScopeType(str, enum.Enum):
    """Scope type for settings - determines inheritance hierarchy."""
    SYSTEM = "system"
    TENANT = "tenant"
    USER = "user"


class AuthDomainType(str, enum.Enum):
    """Authentication domain type."""
    ADMIN = "admin"
    MEMBERS = "members"
    WEBAPP = "webapp"


class SSOProviderType(str, enum.Enum):
    """SSO provider protocol type."""
    SAML = "saml"
    OIDC = "oidc"
    OAUTH2 = "oauth2"


class NotificationChannelType(str, enum.Enum):
    """Notification channel type."""
    SMTP = "smtp"
    WEBHOOK = "webhook"
    SLACK = "slack"
    FEISHU = "feishu"
    WECOM = "wecom"
    DINGTALK = "dingtalk"


class SettingsKV(Base):
    """
    Universal key-value settings store.

    Supports hierarchical settings with system -> tenant -> user inheritance.
    Sensitive values are stored encrypted in value_enc.
    """
    __tablename__ = "settings_kv"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scope_type: Mapped[SettingsScopeType] = mapped_column(
        Enum(SettingsScopeType),
        nullable=False,
    )

    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,  # NULL for system scope
    )

    key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    value_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    value_enc: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    is_encrypted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "key", name="uq_settings_kv_scope_key"),
        Index("ix_settings_kv_scope_key", "scope_type", "scope_id", "key"),
    )

    def to_dict(self, include_value: bool = True) -> dict:
        """Convert to dictionary. Encrypted values are never included."""
        result = {
            "id": str(self.id),
            "scope_type": self.scope_type.value,
            "scope_id": str(self.scope_id) if self.scope_id else None,
            "key": self.key,
            "is_encrypted": self.is_encrypted,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_value and not self.is_encrypted:
            result["value"] = self.value_json
        return result


class SSOProvider(Base):
    """
    SSO Identity Provider configuration.

    Supports SAML, OIDC, and OAuth2 providers.
    Sensitive secrets are stored encrypted in secrets_enc.
    """
    __tablename__ = "sso_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scope_type: Mapped[SettingsScopeType] = mapped_column(
        Enum(SettingsScopeType),
        default=SettingsScopeType.SYSTEM,
        nullable=False,
    )

    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    domain: Mapped[AuthDomainType] = mapped_column(
        Enum(AuthDomainType),
        default=AuthDomainType.ADMIN,
        nullable=False,
    )

    provider_type: Mapped[SSOProviderType] = mapped_column(
        Enum(SSOProviderType),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    display_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    order: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
    )

    config_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    secrets_enc: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    state_tokens: Mapped[list["SSOStateToken"]] = relationship(
        "SSOStateToken",
        back_populates="provider",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "domain", "name", name="uq_sso_providers_scope_domain_name"),
        Index("ix_sso_providers_domain_enabled", "domain", "enabled"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary. Secrets are never included."""
        return {
            "id": str(self.id),
            "scope_type": self.scope_type.value,
            "scope_id": str(self.scope_id) if self.scope_id else None,
            "domain": self.domain.value,
            "provider_type": self.provider_type.value,
            "name": self.name,
            "display_name": self.display_name,
            "icon": self.icon,
            "enabled": self.enabled,
            "order": self.order,
            "config": self.config_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AuthPolicy(Base):
    """
    Authentication policy per domain (admin/members/webapp).

    Controls which authentication methods are enabled and session settings.
    """
    __tablename__ = "auth_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    domain: Mapped[AuthDomainType] = mapped_column(
        Enum(AuthDomainType),
        nullable=False,
    )

    scope_type: Mapped[SettingsScopeType] = mapped_column(
        Enum(SettingsScopeType),
        default=SettingsScopeType.SYSTEM,
        nullable=False,
    )

    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Login methods
    email_password_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    email_code_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    sso_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Session settings
    session_timeout_days: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Auto-create admin (only for admin domain)
    auto_create_admin_on_first_sso: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    auto_create_admin_email_domains: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String(255)),
        nullable=True,
    )

    # Members-specific settings
    self_signup_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    signup_auto_create_personal_space: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    allowed_email_domains: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String(255)),
        nullable=True,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("domain", "scope_type", "scope_id", name="uq_auth_policies_domain_scope"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "domain": self.domain.value,
            "scope_type": self.scope_type.value,
            "scope_id": str(self.scope_id) if self.scope_id else None,
            "email_password_enabled": self.email_password_enabled,
            "email_code_enabled": self.email_code_enabled,
            "sso_enabled": self.sso_enabled,
            "session_timeout_days": self.session_timeout_days,
            "auto_create_admin_on_first_sso": self.auto_create_admin_on_first_sso,
            "auto_create_admin_email_domains": self.auto_create_admin_email_domains,
            "self_signup_enabled": self.self_signup_enabled,
            "signup_auto_create_personal_space": self.signup_auto_create_personal_space,
            "allowed_email_domains": self.allowed_email_domains,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserProfile(Base):
    """
    Extended user profile data.

    Stores avatar, locale, timezone, and user preferences.
    """
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    display_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    avatar_object_key: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    locale: Mapped[Optional[str]] = mapped_column(
        String(10),
        default="zh-CN",
        nullable=True,
    )

    timezone: Mapped[Optional[str]] = mapped_column(
        String(50),
        default="Asia/Shanghai",
        nullable=True,
    )

    preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "user_id": str(self.user_id),
            "display_name": self.display_name,
            "avatar_object_key": self.avatar_object_key,
            "locale": self.locale,
            "timezone": self.timezone,
            "preferences": self.preferences,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BrandingSettings(Base):
    """
    Platform branding configuration.

    Stores logo, favicon, brand name, and visual customization.
    """
    __tablename__ = "branding_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scope_type: Mapped[SettingsScopeType] = mapped_column(
        Enum(SettingsScopeType),
        default=SettingsScopeType.SYSTEM,
        nullable=False,
    )

    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    brand_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    logo_object_key: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    favicon_object_key: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    login_page_title: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    dashboard_title: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    browser_title_template: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    login_background_object_key: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    primary_color: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    color_scheme_locked: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    custom_css: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", name="uq_branding_settings_scope"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "scope_type": self.scope_type.value,
            "scope_id": str(self.scope_id) if self.scope_id else None,
            "brand_name": self.brand_name,
            "logo_object_key": self.logo_object_key,
            "favicon_object_key": self.favicon_object_key,
            "login_page_title": self.login_page_title,
            "dashboard_title": self.dashboard_title,
            "browser_title_template": self.browser_title_template,
            "login_background_object_key": self.login_background_object_key,
            "primary_color": self.primary_color,
            "color_scheme_locked": self.color_scheme_locked,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class NotificationChannel(Base):
    """
    Notification channel configuration.

    Supports SMTP, webhooks, and enterprise IM integrations.
    """
    __tablename__ = "notification_channels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scope_type: Mapped[SettingsScopeType] = mapped_column(
        Enum(SettingsScopeType),
        default=SettingsScopeType.SYSTEM,
        nullable=False,
    )

    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    channel_type: Mapped[NotificationChannelType] = mapped_column(
        Enum(NotificationChannelType),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    config_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    secrets_enc: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    last_test_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_test_success: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    subscriptions: Mapped[list["NotificationSubscription"]] = relationship(
        "NotificationSubscription",
        back_populates="channel",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "channel_type", "name", name="uq_notification_channels_scope_type_name"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "scope_type": self.scope_type.value,
            "scope_id": str(self.scope_id) if self.scope_id else None,
            "channel_type": self.channel_type.value,
            "name": self.name,
            "enabled": self.enabled,
            "config": self.config_json,
            "last_test_at": self.last_test_at.isoformat() if self.last_test_at else None,
            "last_test_success": self.last_test_success,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class NotificationSubscription(Base):
    """
    Event subscription for notification channels.
    """
    __tablename__ = "notification_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scope_type: Mapped[SettingsScopeType] = mapped_column(
        Enum(SettingsScopeType),
        nullable=False,
    )

    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    digest_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    digest_interval_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    filters: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    channel: Mapped["NotificationChannel"] = relationship(
        "NotificationChannel",
        back_populates="subscriptions",
    )

    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "channel_id", "event_type", name="uq_notification_subscriptions"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "scope_type": self.scope_type.value,
            "scope_id": str(self.scope_id) if self.scope_id else None,
            "channel_id": str(self.channel_id),
            "event_type": self.event_type,
            "enabled": self.enabled,
            "digest_enabled": self.digest_enabled,
            "digest_interval_minutes": self.digest_interval_minutes,
            "filters": self.filters,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SecurityPolicy(Base):
    """
    Security and compliance policy settings.
    """
    __tablename__ = "security_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scope_type: Mapped[SettingsScopeType] = mapped_column(
        Enum(SettingsScopeType),
        default=SettingsScopeType.SYSTEM,
        nullable=False,
    )

    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Session policies
    session_idle_timeout_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )

    session_absolute_timeout_days: Mapped[int] = mapped_column(
        Integer,
        default=7,
        nullable=False,
    )

    max_concurrent_sessions: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )

    force_logout_on_password_change: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Password policies
    password_min_length: Mapped[int] = mapped_column(
        Integer,
        default=8,
        nullable=False,
    )

    password_require_uppercase: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    password_require_lowercase: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    password_require_digit: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    password_require_special: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    password_history_count: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )

    password_expiry_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Login security
    max_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )

    lockout_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=15,
        nullable=False,
    )

    # IP access control
    ip_allowlist: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )

    ip_denylist: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )

    ip_access_control_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Audit logging
    audit_log_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    audit_log_retention_days: Mapped[int] = mapped_column(
        Integer,
        default=90,
        nullable=False,
    )

    # Egress control
    egress_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    egress_allowed_domains: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String(255)),
        nullable=True,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", name="uq_security_policies_scope"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "scope_type": self.scope_type.value,
            "scope_id": str(self.scope_id) if self.scope_id else None,
            "session_idle_timeout_minutes": self.session_idle_timeout_minutes,
            "session_absolute_timeout_days": self.session_absolute_timeout_days,
            "max_concurrent_sessions": self.max_concurrent_sessions,
            "force_logout_on_password_change": self.force_logout_on_password_change,
            "password_min_length": self.password_min_length,
            "password_require_uppercase": self.password_require_uppercase,
            "password_require_lowercase": self.password_require_lowercase,
            "password_require_digit": self.password_require_digit,
            "password_require_special": self.password_require_special,
            "password_history_count": self.password_history_count,
            "password_expiry_days": self.password_expiry_days,
            "max_login_attempts": self.max_login_attempts,
            "lockout_duration_minutes": self.lockout_duration_minutes,
            "ip_allowlist": self.ip_allowlist,
            "ip_denylist": self.ip_denylist,
            "ip_access_control_enabled": self.ip_access_control_enabled,
            "audit_log_enabled": self.audit_log_enabled,
            "audit_log_retention_days": self.audit_log_retention_days,
            "egress_enabled": self.egress_enabled,
            "egress_allowed_domains": self.egress_allowed_domains,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SettingsAuditLog(Base):
    """
    Audit log for settings changes.
    """
    __tablename__ = "settings_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scope_type: Mapped[SettingsScopeType] = mapped_column(
        Enum(SettingsScopeType),
        nullable=False,
    )

    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    actor_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    resource_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    old_value: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    new_value: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    request_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_settings_audit_logs_scope_created", "scope_type", "scope_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "scope_type": self.scope_type.value,
            "scope_id": str(self.scope_id) if self.scope_id else None,
            "actor_id": str(self.actor_id),
            "actor_email": self.actor_email,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_key": self.resource_key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SSOStateToken(Base):
    """
    CSRF state token for SSO flows.

    Stores state, nonce, and PKCE code verifier for OAuth2/OIDC flows.
    """
    __tablename__ = "sso_state_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    state: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sso_providers.id", ondelete="CASCADE"),
        nullable=False,
    )

    nonce: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    code_verifier: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    redirect_uri: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    extra_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    provider: Mapped["SSOProvider"] = relationship(
        "SSOProvider",
        back_populates="state_tokens",
    )

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at


class FeatureFlag(Base):
    """
    Feature flag for enabling/disabling platform features.
    """
    __tablename__ = "feature_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scope_type: Mapped[SettingsScopeType] = mapped_column(
        Enum(SettingsScopeType),
        default=SettingsScopeType.SYSTEM,
        nullable=False,
    )

    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    flag_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    flag_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "flag_key", name="uq_feature_flags_scope_key"),
        Index("ix_feature_flags_scope_key", "scope_type", "scope_id", "flag_key"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "scope_type": self.scope_type.value,
            "scope_id": str(self.scope_id) if self.scope_id else None,
            "flag_key": self.flag_key,
            "enabled": self.enabled,
            "description": self.description,
            "metadata": self.flag_metadata,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
