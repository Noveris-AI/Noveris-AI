"""
SSO configuration and provider management.

Parses SSO provider configurations from environment variables.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class OIDCProvider:
    """OIDC provider configuration."""

    provider_id: str
    provider_name: str
    enabled: bool
    client_id: str
    client_secret: str
    discovery_url: str
    scope: str = "openid email profile"
    authorization_endpoint: Optional[str] = None
    token_endpoint: Optional[str] = None
    userinfo_endpoint: Optional[str] = None
    jwks_uri: Optional[str] = None

    @classmethod
    def from_config_string(cls, config: str) -> "OIDCProvider":
        """
        Parse OIDC provider from config string.

        Format: provider_id|provider_name|enabled|key=value|...

        Example: google|Google|true|client_id=xxx|client_secret=yyy|discovery_url=https://...
        """
        parts = config.split("|")
        if len(parts) < 4:
            raise ValueError(f"Invalid OIDC provider config: {config}")

        provider_id = parts[0].strip()
        provider_name = parts[1].strip()
        enabled = parts[2].strip().lower() == "true"

        # Parse key-value pairs
        config_dict = {}
        for part in parts[3:]:
            if "=" in part:
                key, value = part.split("=", 1)
                config_dict[key.strip()] = value.strip()

        return cls(
            provider_id=provider_id,
            provider_name=provider_name,
            enabled=enabled,
            client_id=config_dict.get("client_id", ""),
            client_secret=config_dict.get("client_secret", ""),
            discovery_url=config_dict.get("discovery_url", ""),
            scope=config_dict.get("scope", "openid email profile"),
        )


@dataclass
class OAuth2Provider:
    """OAuth2 provider configuration."""

    provider_id: str
    provider_name: str
    enabled: bool
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    user_url: str
    scope: str = "user:email"

    @classmethod
    def from_config_string(cls, config: str) -> "OAuth2Provider":
        """
        Parse OAuth2 provider from config string.

        Format: provider_id|provider_name|enabled|key=value|...
        """
        parts = config.split("|")
        if len(parts) < 4:
            raise ValueError(f"Invalid OAuth2 provider config: {config}")

        provider_id = parts[0].strip()
        provider_name = parts[1].strip()
        enabled = parts[2].strip().lower() == "true"

        # Parse key-value pairs
        config_dict = {}
        for part in parts[3:]:
            if "=" in part:
                key, value = part.split("=", 1)
                config_dict[key.strip()] = value.strip()

        return cls(
            provider_id=provider_id,
            provider_name=provider_name,
            enabled=enabled,
            client_id=config_dict.get("client_id", ""),
            client_secret=config_dict.get("client_secret", ""),
            authorization_url=config_dict.get("auth_url", ""),
            token_url=config_dict.get("token_url", ""),
            user_url=config_dict.get("user_url", ""),
            scope=config_dict.get("scope", "user:email"),
        )


@dataclass
class SAMLProvider:
    """SAML provider configuration."""

    provider_id: str
    provider_name: str
    enabled: bool
    entity_id: str
    metadata_url: Optional[str] = None
    metadata_xml: Optional[str] = None
    acs_url: str = ""
    x509_cert: Optional[str] = None

    @classmethod
    def from_config_string(cls, config: str, acs_base_url: str) -> "SAMLProvider":
        """
        Parse SAML provider from config string.

        Format: provider_id|provider_name|enabled|key=value|...
        """
        parts = config.split("|")
        if len(parts) < 4:
            raise ValueError(f"Invalid SAML provider config: {config}")

        provider_id = parts[0].strip()
        provider_name = parts[1].strip()
        enabled = parts[2].strip().lower() == "true"

        # Parse key-value pairs
        config_dict = {}
        for part in parts[3:]:
            if "=" in part:
                key, value = part.split("=", 1)
                config_dict[key.strip()] = value.strip()

        return cls(
            provider_id=provider_id,
            provider_name=provider_name,
            enabled=enabled,
            entity_id=config_dict.get("entity_id", ""),
            metadata_url=config_dict.get("metadata_url"),
            metadata_xml=config_dict.get("metadata_xml"),
            acs_url=config_dict.get("acs_url", f"{acs_base_url}/saml/acs"),
            x509_cert=config_dict.get("x509_cert"),
        )


class SSOConfig:
    """SSO configuration manager."""

    def __init__(self):
        """Initialize SSO configuration from environment variables."""
        from app.core.config import settings

        self.oidc_providers: Dict[str, OIDCProvider] = {}
        self.oauth2_providers: Dict[str, OAuth2Provider] = {}
        self.saml_providers: Dict[str, SAMLProvider] = {}

        # Parse OIDC providers
        if settings.sso.oidc_providers:
            for provider_str in settings.sso.oidc_providers.split(";"):
                provider_str = provider_str.strip()
                if provider_str:
                    provider = OIDCProvider.from_config_string(provider_str)
                    if provider.enabled:
                        self.oidc_providers[provider.provider_id] = provider

        # Parse OAuth2 providers
        if settings.sso.oauth2_providers:
            for provider_str in settings.sso.oauth2_providers.split(";"):
                provider_str = provider_str.strip()
                if provider_str:
                    provider = OAuth2Provider.from_config_string(provider_str)
                    if provider.enabled:
                        self.oauth2_providers[provider.provider_id] = provider

        # Parse SAML providers
        if settings.sso.saml_providers:
            for provider_str in settings.sso.saml_providers.split(";"):
                provider_str = provider_str.strip()
                if provider_str:
                    provider = SAMLProvider.from_config_string(
                        provider_str,
                        f"{settings.api_host}://{settings.api_port}/api/v1/auth/sso",
                    )
                    if provider.enabled:
                        self.saml_providers[provider.provider_id] = provider

    @property
    def enabled_providers(self) -> List[Dict[str, str]]:
        """Get list of enabled SSO providers."""
        providers = []

        for provider in self.oidc_providers.values():
            providers.append({
                "id": provider.provider_id,
                "name": provider.provider_name,
                "type": "oidc",
            })

        for provider in self.oauth2_providers.values():
            providers.append({
                "id": provider.provider_id,
                "name": provider.provider_name,
                "type": "oauth2",
            })

        for provider in self.saml_providers.values():
            providers.append({
                "id": provider.provider_id,
                "name": provider.provider_name,
                "type": "saml",
            })

        return providers

    def get_oidc_provider(self, provider_id: str) -> Optional[OIDCProvider]:
        """Get OIDC provider by ID."""
        return self.oidc_providers.get(provider_id)

    def get_oauth2_provider(self, provider_id: str) -> Optional[OAuth2Provider]:
        """Get OAuth2 provider by ID."""
        return self.oauth2_providers.get(provider_id)

    def get_saml_provider(self, provider_id: str) -> Optional[SAMLProvider]:
        """Get SAML provider by ID."""
        return self.saml_providers.get(provider_id)


# Global SSO configuration instance
sso_config = SSOConfig()
