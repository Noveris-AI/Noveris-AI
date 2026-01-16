"""
Settings service for managing platform settings.

Provides a unified interface for managing:
- Key-value settings
- Authentication policies
- SSO providers
- Security policies
- Branding
- Notification channels

Implements:
- Settings inheritance (system -> tenant -> user)
- Encryption for sensitive values
- Audit logging
- Validation and safety guards
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict, Tuple

from sqlalchemy import select, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.settings import (
    SettingsKV,
    SSOProvider,
    AuthPolicy,
    UserProfile,
    BrandingSettings,
    NotificationChannel,
    NotificationSubscription,
    SecurityPolicy,
    SettingsAuditLog,
    FeatureFlag,
    SettingsScopeType,
    AuthDomainType,
    SSOProviderType,
    NotificationChannelType,
)
from app.settings.encryption import (
    get_settings_encryption,
    is_sensitive_key,
    redact_sensitive_fields,
)


UTC = timezone.utc


class SettingsValidationError(Exception):
    """Raised when settings validation fails."""
    pass


class SettingsSecurityError(Exception):
    """Raised when a security constraint is violated."""
    pass


class SettingsService:
    """
    Service for managing platform settings.

    Handles CRUD operations, validation, encryption, and audit logging.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._encryption = get_settings_encryption()

    # ===========================================
    # Key-Value Settings
    # ===========================================

    async def get_setting(
        self,
        key: str,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
        inherit: bool = True,
    ) -> Optional[Any]:
        """
        Get a setting value.

        Args:
            key: Setting key
            scope_type: Scope type (system, tenant, user)
            scope_id: Scope ID (None for system scope)
            inherit: If True, inherit from parent scopes if not found

        Returns:
            Setting value or None if not found
        """
        # Try to get the setting at the requested scope
        result = await self._get_setting_record(key, scope_type, scope_id)
        if result:
            return self._get_setting_value(result)

        # If inherit is enabled, try parent scopes
        if inherit:
            if scope_type == SettingsScopeType.USER:
                # Try tenant scope (if scope_id is user_id, we'd need tenant_id)
                # For simplicity, fall back to system
                result = await self._get_setting_record(
                    key, SettingsScopeType.SYSTEM, None
                )
                if result:
                    return self._get_setting_value(result)
            elif scope_type == SettingsScopeType.TENANT:
                # Try system scope
                result = await self._get_setting_record(
                    key, SettingsScopeType.SYSTEM, None
                )
                if result:
                    return self._get_setting_value(result)

        return None

    async def _get_setting_record(
        self,
        key: str,
        scope_type: SettingsScopeType,
        scope_id: Optional[uuid.UUID],
    ) -> Optional[SettingsKV]:
        """Get a setting record from the database."""
        query = select(SettingsKV).where(
            and_(
                SettingsKV.key == key,
                SettingsKV.scope_type == scope_type,
                SettingsKV.scope_id == scope_id if scope_id else SettingsKV.scope_id.is_(None),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def _get_setting_value(self, setting: SettingsKV) -> Any:
        """Extract the value from a setting record, decrypting if necessary."""
        if setting.is_encrypted and setting.value_enc:
            return self._encryption.decrypt(setting.value_enc)
        return setting.value_json

    async def set_setting(
        self,
        key: str,
        value: Any,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> SettingsKV:
        """
        Set a setting value.

        Args:
            key: Setting key
            value: Value to set
            scope_type: Scope type
            scope_id: Scope ID
            actor_id: ID of user making the change
            actor_email: Email of user making the change
            ip_address: Request IP address
            user_agent: Request user agent

        Returns:
            Updated or created setting record
        """
        # Check if setting exists
        existing = await self._get_setting_record(key, scope_type, scope_id)

        # Determine if value should be encrypted
        should_encrypt = is_sensitive_key(key)

        # Prepare values
        value_json = None if should_encrypt else value
        value_enc = self._encryption.encrypt(value) if should_encrypt else None

        if existing:
            # Update existing
            old_value = self._get_setting_value(existing) if not should_encrypt else "[ENCRYPTED]"

            existing.value_json = value_json
            existing.value_enc = value_enc
            existing.is_encrypted = should_encrypt
            existing.version += 1
            existing.updated_by = actor_id

            # Audit log
            await self._create_audit_log(
                scope_type=scope_type,
                scope_id=scope_id,
                actor_id=actor_id,
                actor_email=actor_email,
                action="update",
                resource_type="settings_kv",
                resource_id=str(existing.id),
                resource_key=key,
                old_value={"value": old_value} if not should_encrypt else None,
                new_value={"value": value} if not should_encrypt else None,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            await self.db.flush()
            return existing
        else:
            # Create new
            setting = SettingsKV(
                scope_type=scope_type,
                scope_id=scope_id,
                key=key,
                value_json=value_json,
                value_enc=value_enc,
                is_encrypted=should_encrypt,
                created_by=actor_id,
                updated_by=actor_id,
            )
            self.db.add(setting)

            # Audit log
            await self._create_audit_log(
                scope_type=scope_type,
                scope_id=scope_id,
                actor_id=actor_id,
                actor_email=actor_email,
                action="create",
                resource_type="settings_kv",
                resource_key=key,
                new_value={"value": value} if not should_encrypt else None,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            await self.db.flush()
            return setting

    async def delete_setting(
        self,
        key: str,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """Delete a setting."""
        existing = await self._get_setting_record(key, scope_type, scope_id)
        if not existing:
            return False

        # Audit log
        await self._create_audit_log(
            scope_type=scope_type,
            scope_id=scope_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action="delete",
            resource_type="settings_kv",
            resource_id=str(existing.id),
            resource_key=key,
            old_value=existing.to_dict(include_value=not existing.is_encrypted),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.delete(existing)
        await self.db.flush()
        return True

    async def get_settings_by_prefix(
        self,
        prefix: str,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Get all settings with a given prefix."""
        query = select(SettingsKV).where(
            and_(
                SettingsKV.key.startswith(prefix),
                SettingsKV.scope_type == scope_type,
                SettingsKV.scope_id == scope_id if scope_id else SettingsKV.scope_id.is_(None),
            )
        )
        result = await self.db.execute(query)
        settings = result.scalars().all()

        return {
            s.key: self._get_setting_value(s) if not s.is_encrypted else "[ENCRYPTED]"
            for s in settings
        }

    # ===========================================
    # Authentication Policies
    # ===========================================

    async def get_auth_policy(
        self,
        domain: AuthDomainType,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
    ) -> Optional[AuthPolicy]:
        """Get authentication policy for a domain."""
        query = select(AuthPolicy).where(
            and_(
                AuthPolicy.domain == domain,
                AuthPolicy.scope_type == scope_type,
                AuthPolicy.scope_id == scope_id if scope_id else AuthPolicy.scope_id.is_(None),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create_auth_policy(
        self,
        domain: AuthDomainType,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
    ) -> AuthPolicy:
        """Get or create authentication policy for a domain."""
        policy = await self.get_auth_policy(domain, scope_type, scope_id)
        if policy:
            return policy

        # Create default policy
        policy = AuthPolicy(
            domain=domain,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        self.db.add(policy)
        await self.db.flush()
        return policy

    async def update_auth_policy(
        self,
        domain: AuthDomainType,
        updates: Dict[str, Any],
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        confirm_risk: bool = False,
    ) -> AuthPolicy:
        """
        Update authentication policy.

        Args:
            domain: Auth domain (admin/members/webapp)
            updates: Dictionary of fields to update
            scope_type: Scope type
            scope_id: Scope ID
            actor_id: Actor user ID
            actor_email: Actor email
            ip_address: Request IP
            user_agent: Request user agent
            confirm_risk: Must be True if disabling all login methods or enabling auto_create_admin

        Returns:
            Updated policy

        Raises:
            SettingsValidationError: If validation fails
            SettingsSecurityError: If security constraints are violated
        """
        policy = await self.get_or_create_auth_policy(domain, scope_type, scope_id)
        old_value = policy.to_dict()

        # Apply updates
        for key, value in updates.items():
            if hasattr(policy, key):
                setattr(policy, key, value)

        # Validate - at least one login method must be enabled
        await self._validate_auth_policy(policy, confirm_risk)

        policy.updated_by = actor_id

        # Audit log
        await self._create_audit_log(
            scope_type=scope_type,
            scope_id=scope_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action="update",
            resource_type="auth_policy",
            resource_id=str(policy.id),
            old_value=old_value,
            new_value=policy.to_dict(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.flush()
        return policy

    async def _validate_auth_policy(
        self,
        policy: AuthPolicy,
        confirm_risk: bool = False,
    ) -> None:
        """
        Validate authentication policy.

        Ensures at least one login method is available.
        """
        # Check if at least one login method is enabled
        has_login_method = (
            policy.email_password_enabled or
            policy.email_code_enabled or
            policy.sso_enabled
        )

        if not has_login_method:
            raise SettingsValidationError(
                "At least one login method must be enabled. "
                "Cannot disable all authentication methods."
            )

        # If only SSO is enabled, verify there's at least one enabled provider
        if policy.sso_enabled and not policy.email_password_enabled and not policy.email_code_enabled:
            providers = await self._get_enabled_sso_providers(
                policy.domain, policy.scope_type, policy.scope_id
            )
            if not providers:
                raise SettingsValidationError(
                    "SSO is the only enabled login method, but no SSO providers are enabled. "
                    "Enable at least one SSO provider or keep another login method enabled."
                )

        # Security check for auto_create_admin
        if policy.auto_create_admin_on_first_sso and policy.domain == AuthDomainType.ADMIN:
            if not confirm_risk:
                raise SettingsSecurityError(
                    "Enabling auto_create_admin_on_first_sso requires explicit confirmation. "
                    "Set confirm_risk=True to proceed. This is a security-sensitive operation."
                )

            # Must have email domain restrictions
            if not policy.auto_create_admin_email_domains:
                raise SettingsValidationError(
                    "auto_create_admin_on_first_sso requires auto_create_admin_email_domains "
                    "to be set for security."
                )

    async def _get_enabled_sso_providers(
        self,
        domain: AuthDomainType,
        scope_type: SettingsScopeType,
        scope_id: Optional[uuid.UUID],
    ) -> List[SSOProvider]:
        """Get enabled SSO providers for a domain."""
        query = select(SSOProvider).where(
            and_(
                SSOProvider.domain == domain,
                SSOProvider.scope_type == scope_type,
                SSOProvider.scope_id == scope_id if scope_id else SSOProvider.scope_id.is_(None),
                SSOProvider.enabled == True,
            )
        ).order_by(SSOProvider.order)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ===========================================
    # SSO Providers
    # ===========================================

    async def get_sso_providers(
        self,
        domain: AuthDomainType,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
        enabled_only: bool = False,
    ) -> List[SSOProvider]:
        """Get SSO providers for a domain."""
        conditions = [
            SSOProvider.domain == domain,
            SSOProvider.scope_type == scope_type,
            SSOProvider.scope_id == scope_id if scope_id else SSOProvider.scope_id.is_(None),
        ]
        if enabled_only:
            conditions.append(SSOProvider.enabled == True)

        query = select(SSOProvider).where(and_(*conditions)).order_by(SSOProvider.order)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_sso_provider(self, provider_id: uuid.UUID) -> Optional[SSOProvider]:
        """Get SSO provider by ID."""
        query = select(SSOProvider).where(SSOProvider.id == provider_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_sso_provider(
        self,
        domain: AuthDomainType,
        provider_type: SSOProviderType,
        name: str,
        config: Dict[str, Any],
        secrets: Optional[Dict[str, Any]] = None,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
        display_name: Optional[str] = None,
        icon: Optional[str] = None,
        enabled: bool = False,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> SSOProvider:
        """Create a new SSO provider."""
        # Encrypt secrets
        secrets_enc = self._encryption.encrypt(secrets) if secrets else None

        provider = SSOProvider(
            scope_type=scope_type,
            scope_id=scope_id,
            domain=domain,
            provider_type=provider_type,
            name=name,
            display_name=display_name or name,
            icon=icon,
            enabled=enabled,
            config_json=config,
            secrets_enc=secrets_enc,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.db.add(provider)

        # Audit log
        await self._create_audit_log(
            scope_type=scope_type,
            scope_id=scope_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action="create",
            resource_type="sso_provider",
            resource_key=name,
            new_value=redact_sensitive_fields(provider.to_dict()),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.flush()
        return provider

    async def update_sso_provider(
        self,
        provider_id: uuid.UUID,
        updates: Dict[str, Any],
        secrets: Optional[Dict[str, Any]] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> SSOProvider:
        """Update an SSO provider."""
        provider = await self.get_sso_provider(provider_id)
        if not provider:
            raise SettingsValidationError(f"SSO provider {provider_id} not found")

        old_value = provider.to_dict()

        # Update fields
        for key, value in updates.items():
            if key == "config_json":
                # Merge config
                provider.config_json = {**(provider.config_json or {}), **value}
            elif hasattr(provider, key) and key not in ("id", "created_at", "created_by"):
                setattr(provider, key, value)

        # Update secrets if provided
        if secrets is not None:
            provider.secrets_enc = self._encryption.encrypt(secrets)

        provider.updated_by = actor_id

        # Audit log
        await self._create_audit_log(
            scope_type=provider.scope_type,
            scope_id=provider.scope_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action="update",
            resource_type="sso_provider",
            resource_id=str(provider.id),
            resource_key=provider.name,
            old_value=redact_sensitive_fields(old_value),
            new_value=redact_sensitive_fields(provider.to_dict()),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.flush()
        return provider

    async def delete_sso_provider(
        self,
        provider_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """Delete an SSO provider."""
        provider = await self.get_sso_provider(provider_id)
        if not provider:
            return False

        # Audit log
        await self._create_audit_log(
            scope_type=provider.scope_type,
            scope_id=provider.scope_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action="delete",
            resource_type="sso_provider",
            resource_id=str(provider.id),
            resource_key=provider.name,
            old_value=redact_sensitive_fields(provider.to_dict()),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.delete(provider)
        await self.db.flush()
        return True

    def get_sso_provider_secrets(self, provider: SSOProvider) -> Optional[Dict[str, Any]]:
        """Decrypt and return SSO provider secrets."""
        if provider.secrets_enc:
            return self._encryption.decrypt(provider.secrets_enc)
        return None

    # ===========================================
    # Security Policies
    # ===========================================

    async def get_security_policy(
        self,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
    ) -> Optional[SecurityPolicy]:
        """Get security policy."""
        query = select(SecurityPolicy).where(
            and_(
                SecurityPolicy.scope_type == scope_type,
                SecurityPolicy.scope_id == scope_id if scope_id else SecurityPolicy.scope_id.is_(None),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create_security_policy(
        self,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
    ) -> SecurityPolicy:
        """Get or create security policy."""
        policy = await self.get_security_policy(scope_type, scope_id)
        if policy:
            return policy

        policy = SecurityPolicy(scope_type=scope_type, scope_id=scope_id)
        self.db.add(policy)
        await self.db.flush()
        return policy

    async def update_security_policy(
        self,
        updates: Dict[str, Any],
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> SecurityPolicy:
        """Update security policy."""
        policy = await self.get_or_create_security_policy(scope_type, scope_id)
        old_value = policy.to_dict()

        for key, value in updates.items():
            if hasattr(policy, key) and key not in ("id", "created_at"):
                setattr(policy, key, value)

        policy.updated_by = actor_id

        # Audit log
        await self._create_audit_log(
            scope_type=scope_type,
            scope_id=scope_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action="update",
            resource_type="security_policy",
            resource_id=str(policy.id),
            old_value=old_value,
            new_value=policy.to_dict(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.flush()
        return policy

    # ===========================================
    # Branding
    # ===========================================

    async def get_branding(
        self,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
    ) -> Optional[BrandingSettings]:
        """Get branding settings."""
        query = select(BrandingSettings).where(
            and_(
                BrandingSettings.scope_type == scope_type,
                BrandingSettings.scope_id == scope_id if scope_id else BrandingSettings.scope_id.is_(None),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create_branding(
        self,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
    ) -> BrandingSettings:
        """Get or create branding settings."""
        branding = await self.get_branding(scope_type, scope_id)
        if branding:
            return branding

        branding = BrandingSettings(scope_type=scope_type, scope_id=scope_id)
        self.db.add(branding)
        await self.db.flush()
        return branding

    async def update_branding(
        self,
        updates: Dict[str, Any],
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> BrandingSettings:
        """Update branding settings."""
        branding = await self.get_or_create_branding(scope_type, scope_id)
        old_value = branding.to_dict()

        for key, value in updates.items():
            if hasattr(branding, key) and key not in ("id", "created_at"):
                setattr(branding, key, value)

        branding.updated_by = actor_id

        # Audit log
        await self._create_audit_log(
            scope_type=scope_type,
            scope_id=scope_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action="update",
            resource_type="branding",
            resource_id=str(branding.id),
            old_value=old_value,
            new_value=branding.to_dict(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.flush()
        return branding

    # ===========================================
    # User Profile
    # ===========================================

    async def get_user_profile(self, user_id: uuid.UUID) -> Optional[UserProfile]:
        """Get user profile."""
        query = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create_user_profile(self, user_id: uuid.UUID) -> UserProfile:
        """Get or create user profile."""
        profile = await self.get_user_profile(user_id)
        if profile:
            return profile

        profile = UserProfile(user_id=user_id)
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def update_user_profile(
        self,
        user_id: uuid.UUID,
        updates: Dict[str, Any],
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserProfile:
        """Update user profile."""
        profile = await self.get_or_create_user_profile(user_id)
        old_value = profile.to_dict()

        for key, value in updates.items():
            if hasattr(profile, key) and key not in ("user_id", "created_at"):
                setattr(profile, key, value)

        # Audit log
        await self._create_audit_log(
            scope_type=SettingsScopeType.USER,
            scope_id=user_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action="update",
            resource_type="user_profile",
            resource_id=str(user_id),
            old_value=old_value,
            new_value=profile.to_dict(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.flush()
        return profile

    # ===========================================
    # Feature Flags
    # ===========================================

    async def get_feature_flag(
        self,
        flag_key: str,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
        inherit: bool = True,
    ) -> bool:
        """
        Get feature flag value.

        Returns False if flag doesn't exist.
        """
        query = select(FeatureFlag).where(
            and_(
                FeatureFlag.flag_key == flag_key,
                FeatureFlag.scope_type == scope_type,
                FeatureFlag.scope_id == scope_id if scope_id else FeatureFlag.scope_id.is_(None),
            )
        )
        result = await self.db.execute(query)
        flag = result.scalar_one_or_none()

        if flag:
            return flag.enabled

        # Inherit from parent scope
        if inherit and scope_type != SettingsScopeType.SYSTEM:
            return await self.get_feature_flag(flag_key, SettingsScopeType.SYSTEM, None, False)

        return False

    async def set_feature_flag(
        self,
        flag_key: str,
        enabled: bool,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> FeatureFlag:
        """Set feature flag."""
        query = select(FeatureFlag).where(
            and_(
                FeatureFlag.flag_key == flag_key,
                FeatureFlag.scope_type == scope_type,
                FeatureFlag.scope_id == scope_id if scope_id else FeatureFlag.scope_id.is_(None),
            )
        )
        result = await self.db.execute(query)
        flag = result.scalar_one_or_none()

        if flag:
            old_value = {"enabled": flag.enabled}
            flag.enabled = enabled
            if description:
                flag.description = description
            flag.updated_by = actor_id
        else:
            old_value = None
            flag = FeatureFlag(
                scope_type=scope_type,
                scope_id=scope_id,
                flag_key=flag_key,
                enabled=enabled,
                description=description,
                created_by=actor_id,
                updated_by=actor_id,
            )
            self.db.add(flag)

        # Audit log
        await self._create_audit_log(
            scope_type=scope_type,
            scope_id=scope_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action="update" if old_value else "create",
            resource_type="feature_flag",
            resource_key=flag_key,
            old_value=old_value,
            new_value={"enabled": enabled},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.flush()
        return flag

    # ===========================================
    # Audit Logging
    # ===========================================

    async def _create_audit_log(
        self,
        scope_type: SettingsScopeType,
        scope_id: Optional[uuid.UUID],
        actor_id: Optional[uuid.UUID],
        actor_email: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        resource_key: Optional[str] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Create an audit log entry."""
        if not actor_id:
            return  # Skip audit log if no actor

        log = SettingsAuditLog(
            scope_type=scope_type,
            scope_id=scope_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_key=resource_key,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        self.db.add(log)

    async def get_audit_logs(
        self,
        scope_type: Optional[SettingsScopeType] = None,
        scope_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SettingsAuditLog]:
        """Get audit logs with optional filters."""
        conditions = []
        if scope_type:
            conditions.append(SettingsAuditLog.scope_type == scope_type)
        if scope_id:
            conditions.append(SettingsAuditLog.scope_id == scope_id)
        if resource_type:
            conditions.append(SettingsAuditLog.resource_type == resource_type)
        if actor_id:
            conditions.append(SettingsAuditLog.actor_id == actor_id)

        query = select(SettingsAuditLog)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(SettingsAuditLog.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())
