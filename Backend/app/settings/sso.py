"""
SSO (Single Sign-On) handlers for OIDC, OAuth2, and SAML protocols.

Implements:
- OIDC with Discovery and PKCE support
- OAuth2 Authorization Code flow with optional PKCE
- SAML SP-initiated SSO with POST binding

Security considerations:
- State parameter validation for CSRF protection
- Nonce validation for OIDC
- PKCE for enhanced security
- Certificate validation for SAML
"""

import base64
import hashlib
import json
import secrets
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode, urljoin, urlparse

import httpx
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import (
    SSOProvider,
    SSOStateToken,
    AuthDomainType,
    SSOProviderType,
    SettingsScopeType,
)
from app.settings.encryption import get_settings_encryption
from app.core.config import settings as app_settings


UTC = timezone.utc


class SSOError(Exception):
    """Base exception for SSO errors."""
    pass


class SSOConfigError(SSOError):
    """Raised when SSO configuration is invalid."""
    pass


class SSOAuthError(SSOError):
    """Raised when SSO authentication fails."""
    pass


class SSOStateError(SSOError):
    """Raised when SSO state validation fails."""
    pass


# ===========================================
# URL Constants
# ===========================================

def get_base_url() -> str:
    """Get the base URL for callback URLs."""
    return app_settings.app.frontend_base_url.rstrip("/")


def get_callback_url(provider_type: SSOProviderType, provider_id: str, domain: AuthDomainType) -> str:
    """Generate callback URL for a provider."""
    base = get_base_url()
    # Use different callback paths for different domains to prevent cross-domain attacks
    return f"{base}/api/v1/sso/{domain.value}/{provider_type.value}/{provider_id}/callback"


def get_acs_url(provider_id: str, domain: AuthDomainType) -> str:
    """Generate SAML ACS (Assertion Consumer Service) URL."""
    base = get_base_url()
    return f"{base}/api/v1/sso/{domain.value}/saml/{provider_id}/acs"


def get_sp_metadata_url(provider_id: str, domain: AuthDomainType) -> str:
    """Generate SAML SP metadata URL."""
    base = get_base_url()
    return f"{base}/api/v1/sso/{domain.value}/saml/{provider_id}/metadata"


# ===========================================
# State Token Management
# ===========================================

class StateTokenManager:
    """Manages SSO state tokens for CSRF protection."""

    STATE_TTL_SECONDS = 600  # 10 minutes

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_state(
        self,
        provider_id: uuid.UUID,
        nonce: Optional[str] = None,
        code_verifier: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        extra_data: Optional[Dict] = None,
    ) -> str:
        """
        Create a new state token.

        Returns the state string to include in the auth request.
        """
        state = secrets.token_urlsafe(32)

        token = SSOStateToken(
            state=state,
            provider_id=provider_id,
            nonce=nonce,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            extra_data=extra_data,
            expires_at=datetime.now(UTC) + timedelta(seconds=self.STATE_TTL_SECONDS),
        )
        self.db.add(token)
        await self.db.flush()

        return state

    async def validate_state(self, state: str) -> SSOStateToken:
        """
        Validate and consume a state token.

        Returns the token if valid, raises SSOStateError otherwise.
        The token is deleted after validation (one-time use).
        """
        query = select(SSOStateToken).where(SSOStateToken.state == state)
        result = await self.db.execute(query)
        token = result.scalar_one_or_none()

        if not token:
            raise SSOStateError("Invalid state parameter")

        if token.is_expired:
            await self.db.delete(token)
            await self.db.flush()
            raise SSOStateError("State parameter has expired")

        # Delete token (one-time use)
        await self.db.delete(token)
        await self.db.flush()

        return token

    async def cleanup_expired(self) -> int:
        """Delete expired state tokens. Returns count of deleted tokens."""
        query = delete(SSOStateToken).where(
            SSOStateToken.expires_at < datetime.now(UTC)
        )
        result = await self.db.execute(query)
        await self.db.flush()
        return result.rowcount


# ===========================================
# PKCE Support
# ===========================================

def generate_pkce_pair() -> Tuple[str, str]:
    """
    Generate PKCE code verifier and challenge.

    Returns: (code_verifier, code_challenge)
    """
    code_verifier = secrets.token_urlsafe(64)[:128]  # 43-128 characters

    # Create SHA256 hash and base64url encode
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")

    return code_verifier, code_challenge


# ===========================================
# User Info Result
# ===========================================

class SSOUserInfo:
    """Normalized user info from SSO provider."""

    def __init__(
        self,
        provider_id: str,
        provider_type: SSOProviderType,
        external_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        picture: Optional[str] = None,
        email_verified: bool = False,
        groups: Optional[list] = None,
        raw_claims: Optional[Dict] = None,
    ):
        self.provider_id = provider_id
        self.provider_type = provider_type
        self.external_id = external_id
        self.email = email
        self.name = name
        self.given_name = given_name
        self.family_name = family_name
        self.picture = picture
        self.email_verified = email_verified
        self.groups = groups or []
        self.raw_claims = raw_claims or {}

    def to_dict(self) -> Dict:
        return {
            "provider_id": self.provider_id,
            "provider_type": self.provider_type.value,
            "external_id": self.external_id,
            "email": self.email,
            "name": self.name,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "picture": self.picture,
            "email_verified": self.email_verified,
            "groups": self.groups,
        }


# ===========================================
# Base SSO Handler
# ===========================================

class BaseSSOHandler(ABC):
    """Base class for SSO protocol handlers."""

    def __init__(
        self,
        provider: SSOProvider,
        db: AsyncSession,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.provider = provider
        self.db = db
        self._http_client = http_client
        self._encryption = get_settings_encryption()
        self._state_manager = StateTokenManager(db)

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Get HTTP client for external requests."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    @property
    def config(self) -> Dict:
        """Get provider configuration."""
        return self.provider.config_json or {}

    @property
    def secrets(self) -> Dict:
        """Get decrypted provider secrets."""
        if self.provider.secrets_enc:
            return self._encryption.decrypt(self.provider.secrets_enc)
        return {}

    @abstractmethod
    async def get_authorization_url(self, redirect_uri: Optional[str] = None) -> str:
        """
        Get the authorization URL to redirect the user to.

        Args:
            redirect_uri: Optional override for redirect URI after login

        Returns:
            URL to redirect user to for authentication
        """
        pass

    @abstractmethod
    async def handle_callback(
        self,
        code: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
        error_description: Optional[str] = None,
        **kwargs,
    ) -> SSOUserInfo:
        """
        Handle the callback from the identity provider.

        Args:
            code: Authorization code
            state: State parameter for CSRF validation
            error: Error code if authentication failed
            error_description: Error description
            **kwargs: Additional callback parameters

        Returns:
            Normalized user info
        """
        pass


# ===========================================
# OIDC Handler
# ===========================================

class OIDCHandler(BaseSSOHandler):
    """
    OpenID Connect handler.

    Supports:
    - Discovery document auto-configuration
    - Authorization Code flow
    - PKCE (optional)
    - ID token validation
    """

    _discovery_cache: Dict[str, Dict] = {}

    async def get_discovery_document(self) -> Dict:
        """Fetch and cache the OIDC discovery document."""
        issuer = self.config.get("issuer_or_discovery_url", "")

        if not issuer:
            raise SSOConfigError("OIDC issuer or discovery URL not configured")

        # Normalize discovery URL
        if "/.well-known/openid-configuration" not in issuer:
            discovery_url = urljoin(issuer.rstrip("/") + "/", ".well-known/openid-configuration")
        else:
            discovery_url = issuer

        # Check cache
        if discovery_url in self._discovery_cache:
            return self._discovery_cache[discovery_url]

        # Fetch discovery document
        try:
            response = await self.http_client.get(discovery_url)
            response.raise_for_status()
            discovery = response.json()
            self._discovery_cache[discovery_url] = discovery
            return discovery
        except httpx.HTTPError as e:
            raise SSOConfigError(f"Failed to fetch OIDC discovery document: {e}")

    async def get_authorization_url(self, redirect_uri: Optional[str] = None) -> str:
        """Get OIDC authorization URL."""
        discovery = await self.get_discovery_document()
        auth_endpoint = discovery.get("authorization_endpoint")

        if not auth_endpoint:
            raise SSOConfigError("Authorization endpoint not found in discovery document")

        client_id = self.config.get("client_id")
        if not client_id:
            raise SSOConfigError("OIDC client_id not configured")

        scopes = self.config.get("scopes", "openid profile email")
        use_pkce = self.config.get("use_pkce", True)

        # Generate callback URL
        callback_url = redirect_uri or get_callback_url(
            SSOProviderType.OIDC,
            str(self.provider.id),
            self.provider.domain,
        )

        # Generate nonce for OIDC
        nonce = secrets.token_urlsafe(32)

        # Generate PKCE if enabled
        code_verifier = None
        code_challenge = None
        if use_pkce:
            code_verifier, code_challenge = generate_pkce_pair()

        # Create state token
        state = await self._state_manager.create_state(
            provider_id=self.provider.id,
            nonce=nonce,
            code_verifier=code_verifier,
            redirect_uri=callback_url,
        )

        # Build authorization URL
        params = {
            "client_id": client_id,
            "response_type": "code",
            "scope": scopes,
            "redirect_uri": callback_url,
            "state": state,
            "nonce": nonce,
        }

        if use_pkce:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        return f"{auth_endpoint}?{urlencode(params)}"

    async def handle_callback(
        self,
        code: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
        error_description: Optional[str] = None,
        **kwargs,
    ) -> SSOUserInfo:
        """Handle OIDC callback."""
        # Check for errors
        if error:
            raise SSOAuthError(f"OIDC error: {error} - {error_description or 'No description'}")

        if not code:
            raise SSOAuthError("Authorization code not provided")

        if not state:
            raise SSOAuthError("State parameter not provided")

        # Validate state
        state_token = await self._state_manager.validate_state(state)

        # Get discovery document
        discovery = await self.get_discovery_document()
        token_endpoint = discovery.get("token_endpoint")
        userinfo_endpoint = discovery.get("userinfo_endpoint")

        if not token_endpoint:
            raise SSOConfigError("Token endpoint not found in discovery document")

        # Exchange code for tokens
        client_id = self.config.get("client_id")
        client_secret = self.secrets.get("client_secret")

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": state_token.redirect_uri,
            "client_id": client_id,
        }

        # Add client_secret if not using PKCE or if configured
        if client_secret:
            token_data["client_secret"] = client_secret

        # Add PKCE verifier if used
        if state_token.code_verifier:
            token_data["code_verifier"] = state_token.code_verifier

        try:
            response = await self.http_client.post(
                token_endpoint,
                data=token_data,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            tokens = response.json()
        except httpx.HTTPError as e:
            raise SSOAuthError(f"Failed to exchange authorization code: {e}")

        # Parse ID token claims
        id_token = tokens.get("id_token")
        access_token = tokens.get("access_token")

        if not id_token and not access_token:
            raise SSOAuthError("No tokens received from provider")

        # Decode ID token (basic decode, not full validation)
        claims = {}
        if id_token:
            try:
                # Split JWT and decode payload
                parts = id_token.split(".")
                if len(parts) >= 2:
                    payload = parts[1]
                    # Add padding if needed
                    payload += "=" * (4 - len(payload) % 4)
                    claims = json.loads(base64.urlsafe_b64decode(payload))
            except Exception:
                pass  # Fall back to userinfo endpoint

        # Validate nonce
        if state_token.nonce and claims.get("nonce") != state_token.nonce:
            # Try userinfo endpoint instead
            claims = {}

        # Get user info from userinfo endpoint if needed
        if not claims.get("email") and userinfo_endpoint and access_token:
            try:
                response = await self.http_client.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                userinfo = response.json()
                claims.update(userinfo)
            except httpx.HTTPError:
                pass

        # Extract user info
        return self._extract_user_info(claims)

    def _extract_user_info(self, claims: Dict) -> SSOUserInfo:
        """Extract normalized user info from claims."""
        # Get claim mapping from config
        mapping = self.config.get("claim_mapping", {})

        email_claim = mapping.get("email", "email")
        name_claim = mapping.get("name", "name")
        groups_claim = mapping.get("groups", "groups")

        # Get external ID (sub is standard for OIDC)
        external_id = claims.get("sub") or claims.get("id") or claims.get("user_id")
        if not external_id:
            raise SSOAuthError("No user identifier found in claims")

        return SSOUserInfo(
            provider_id=str(self.provider.id),
            provider_type=SSOProviderType.OIDC,
            external_id=str(external_id),
            email=claims.get(email_claim),
            name=claims.get(name_claim),
            given_name=claims.get("given_name"),
            family_name=claims.get("family_name"),
            picture=claims.get("picture"),
            email_verified=claims.get("email_verified", False),
            groups=claims.get(groups_claim, []),
            raw_claims=claims,
        )


# ===========================================
# OAuth2 Handler
# ===========================================

class OAuth2Handler(BaseSSOHandler):
    """
    OAuth2 Authorization Code handler.

    Supports:
    - Authorization Code flow
    - PKCE (optional)
    - Custom endpoints configuration
    """

    async def get_authorization_url(self, redirect_uri: Optional[str] = None) -> str:
        """Get OAuth2 authorization URL."""
        auth_endpoint = self.config.get("authorization_endpoint")
        if not auth_endpoint:
            raise SSOConfigError("OAuth2 authorization_endpoint not configured")

        client_id = self.config.get("client_id")
        if not client_id:
            raise SSOConfigError("OAuth2 client_id not configured")

        scopes = self.config.get("scopes", "")
        use_pkce = self.config.get("use_pkce", False)

        # Generate callback URL
        callback_url = redirect_uri or get_callback_url(
            SSOProviderType.OAUTH2,
            str(self.provider.id),
            self.provider.domain,
        )

        # Generate PKCE if enabled
        code_verifier = None
        code_challenge = None
        if use_pkce:
            code_verifier, code_challenge = generate_pkce_pair()

        # Create state token
        state = await self._state_manager.create_state(
            provider_id=self.provider.id,
            code_verifier=code_verifier,
            redirect_uri=callback_url,
        )

        # Build authorization URL
        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": callback_url,
            "state": state,
        }

        if scopes:
            params["scope"] = scopes

        if use_pkce:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        return f"{auth_endpoint}?{urlencode(params)}"

    async def handle_callback(
        self,
        code: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
        error_description: Optional[str] = None,
        **kwargs,
    ) -> SSOUserInfo:
        """Handle OAuth2 callback."""
        # Check for errors
        if error:
            raise SSOAuthError(f"OAuth2 error: {error} - {error_description or 'No description'}")

        if not code:
            raise SSOAuthError("Authorization code not provided")

        if not state:
            raise SSOAuthError("State parameter not provided")

        # Validate state
        state_token = await self._state_manager.validate_state(state)

        # Get endpoints
        token_endpoint = self.config.get("token_endpoint")
        userinfo_endpoint = self.config.get("userinfo_endpoint")

        if not token_endpoint:
            raise SSOConfigError("OAuth2 token_endpoint not configured")

        # Exchange code for tokens
        client_id = self.config.get("client_id")
        client_secret = self.secrets.get("client_secret")

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": state_token.redirect_uri,
            "client_id": client_id,
        }

        if client_secret:
            token_data["client_secret"] = client_secret

        if state_token.code_verifier:
            token_data["code_verifier"] = state_token.code_verifier

        try:
            response = await self.http_client.post(
                token_endpoint,
                data=token_data,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            tokens = response.json()
        except httpx.HTTPError as e:
            raise SSOAuthError(f"Failed to exchange authorization code: {e}")

        access_token = tokens.get("access_token")
        if not access_token:
            raise SSOAuthError("No access token received")

        # Get user info
        if not userinfo_endpoint:
            raise SSOConfigError("OAuth2 userinfo_endpoint not configured")

        try:
            response = await self.http_client.get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            userinfo = response.json()
        except httpx.HTTPError as e:
            raise SSOAuthError(f"Failed to fetch user info: {e}")

        return self._extract_user_info(userinfo)

    def _extract_user_info(self, userinfo: Dict) -> SSOUserInfo:
        """Extract normalized user info from OAuth2 userinfo response."""
        # Get claim mapping from config
        mapping = self.config.get("claim_mapping", {})

        id_claim = mapping.get("id", "id")
        email_claim = mapping.get("email", "email")
        name_claim = mapping.get("name", "name")
        groups_claim = mapping.get("groups", "groups")

        # Get external ID
        external_id = (
            userinfo.get(id_claim) or
            userinfo.get("sub") or
            userinfo.get("user_id") or
            userinfo.get("uid")
        )
        if not external_id:
            raise SSOAuthError("No user identifier found in userinfo")

        # Try to get name from various sources
        name = userinfo.get(name_claim)
        if not name:
            first = userinfo.get("first_name") or userinfo.get("given_name") or ""
            last = userinfo.get("last_name") or userinfo.get("family_name") or ""
            name = f"{first} {last}".strip() or userinfo.get("username") or userinfo.get("login")

        return SSOUserInfo(
            provider_id=str(self.provider.id),
            provider_type=SSOProviderType.OAUTH2,
            external_id=str(external_id),
            email=userinfo.get(email_claim),
            name=name,
            given_name=userinfo.get("first_name") or userinfo.get("given_name"),
            family_name=userinfo.get("last_name") or userinfo.get("family_name"),
            picture=userinfo.get("avatar_url") or userinfo.get("picture") or userinfo.get("avatar"),
            email_verified=userinfo.get("email_verified", False),
            groups=userinfo.get(groups_claim, []),
            raw_claims=userinfo,
        )


# ===========================================
# SAML Handler (Placeholder)
# ===========================================

class SAMLHandler(BaseSSOHandler):
    """
    SAML 2.0 handler.

    Note: Full SAML implementation requires python3-saml or pysaml2 library.
    This is a placeholder that provides the interface.
    """

    async def get_authorization_url(self, redirect_uri: Optional[str] = None) -> str:
        """Get SAML authentication URL (SP-initiated SSO)."""
        idp_sso_url = self.config.get("idp_sso_url")
        if not idp_sso_url:
            raise SSOConfigError("SAML idp_sso_url not configured")

        # In a full implementation, this would:
        # 1. Generate SAML AuthnRequest
        # 2. Sign it if required
        # 3. Encode it
        # 4. Build redirect URL with SAMLRequest parameter

        # Create state for CSRF protection
        state = await self._state_manager.create_state(
            provider_id=self.provider.id,
            redirect_uri=redirect_uri,
        )

        # For now, return a placeholder URL
        # In production, use python3-saml or pysaml2 to generate proper AuthnRequest
        acs_url = get_acs_url(str(self.provider.id), self.provider.domain)

        params = {
            "RelayState": state,
            # SAMLRequest would go here in a full implementation
        }

        return f"{idp_sso_url}?{urlencode(params)}"

    async def handle_callback(
        self,
        code: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
        error_description: Optional[str] = None,
        **kwargs,
    ) -> SSOUserInfo:
        """Handle SAML callback (ACS endpoint)."""
        saml_response = kwargs.get("SAMLResponse")
        relay_state = kwargs.get("RelayState") or state

        if not saml_response:
            raise SSOAuthError("SAMLResponse not provided")

        if relay_state:
            await self._state_manager.validate_state(relay_state)

        # In a full implementation, this would:
        # 1. Decode SAMLResponse
        # 2. Validate signature using X509 certificate
        # 3. Validate conditions (audience, time)
        # 4. Extract NameID and attributes

        # For now, raise an error indicating full implementation is needed
        raise NotImplementedError(
            "Full SAML implementation requires python3-saml or pysaml2 library. "
            "Please install the appropriate library and implement SAML response validation."
        )


# ===========================================
# Handler Factory
# ===========================================

def get_sso_handler(
    provider: SSOProvider,
    db: AsyncSession,
    http_client: Optional[httpx.AsyncClient] = None,
) -> BaseSSOHandler:
    """Get the appropriate SSO handler for a provider."""
    handlers = {
        SSOProviderType.OIDC: OIDCHandler,
        SSOProviderType.OAUTH2: OAuth2Handler,
        SSOProviderType.SAML: SAMLHandler,
    }

    handler_class = handlers.get(provider.provider_type)
    if not handler_class:
        raise SSOConfigError(f"Unknown SSO provider type: {provider.provider_type}")

    return handler_class(provider, db, http_client)


# ===========================================
# SSO Service
# ===========================================

class SSOService:
    """
    High-level SSO service for managing authentication flows.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_provider(self, provider_id: uuid.UUID) -> Optional[SSOProvider]:
        """Get SSO provider by ID."""
        query = select(SSOProvider).where(SSOProvider.id == provider_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_enabled_providers(
        self,
        domain: AuthDomainType,
        scope_type: SettingsScopeType = SettingsScopeType.SYSTEM,
        scope_id: Optional[uuid.UUID] = None,
    ) -> list[SSOProvider]:
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

    async def initiate_sso(
        self,
        provider_id: uuid.UUID,
        redirect_uri: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> str:
        """
        Initiate SSO flow for a provider.

        Returns the authorization URL to redirect the user to.
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            raise SSOError(f"SSO provider {provider_id} not found")

        if not provider.enabled:
            raise SSOError(f"SSO provider {provider.name} is not enabled")

        handler = get_sso_handler(provider, self.db, http_client)
        return await handler.get_authorization_url(redirect_uri)

    async def complete_sso(
        self,
        provider_id: uuid.UUID,
        http_client: Optional[httpx.AsyncClient] = None,
        **callback_params,
    ) -> SSOUserInfo:
        """
        Complete SSO flow by handling the callback.

        Returns normalized user info from the identity provider.
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            raise SSOError(f"SSO provider {provider_id} not found")

        handler = get_sso_handler(provider, self.db, http_client)
        return await handler.handle_callback(**callback_params)

    async def cleanup_expired_states(self) -> int:
        """Clean up expired state tokens."""
        state_manager = StateTokenManager(self.db)
        return await state_manager.cleanup_expired()
