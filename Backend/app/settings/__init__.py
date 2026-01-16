"""
Settings module for the Noveris AI platform.

Provides a comprehensive settings system with:
- System-wide, tenant-level, and user-level settings
- SSO provider management (OIDC, OAuth2, SAML)
- Authentication policies
- Security policies
- Notification channels
- Branding configuration
- Feature flags

All sensitive values are encrypted at rest using Fernet encryption.
"""

from app.settings.encryption import (
    SettingsEncryption,
    SettingsEncryptionError,
    EncryptionKeyError,
    DecryptionError,
    get_settings_encryption,
    encrypt_sensitive_value,
    decrypt_sensitive_value,
    mask_sensitive_string,
    is_sensitive_key,
    redact_sensitive_fields,
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
    SSOStateError,
    SSOUserInfo,
    OIDCHandler,
    OAuth2Handler,
    SAMLHandler,
    get_sso_handler,
)

from app.settings.routes import router as settings_router
from app.settings.sso_routes import router as sso_router

__all__ = [
    # Encryption
    "SettingsEncryption",
    "SettingsEncryptionError",
    "EncryptionKeyError",
    "DecryptionError",
    "get_settings_encryption",
    "encrypt_sensitive_value",
    "decrypt_sensitive_value",
    "mask_sensitive_string",
    "is_sensitive_key",
    "redact_sensitive_fields",
    # Service
    "SettingsService",
    "SettingsValidationError",
    "SettingsSecurityError",
    # SSO
    "SSOService",
    "SSOError",
    "SSOConfigError",
    "SSOAuthError",
    "SSOStateError",
    "SSOUserInfo",
    "OIDCHandler",
    "OAuth2Handler",
    "SAMLHandler",
    "get_sso_handler",
    # Routers
    "settings_router",
    "sso_router",
]
