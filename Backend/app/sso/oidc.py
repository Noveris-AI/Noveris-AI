"""
OIDC (OpenID Connect) SSO implementation.
"""

import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.sso.config import OIDCProvider


class OIDCService:
    """Service for handling OIDC authentication flow."""

    def __init__(self, provider: OIDCProvider):
        """
        Initialize OIDC service.

        Args:
            provider: OIDC provider configuration
        """
        self.provider = provider
        self._discovery_cache: Optional[Dict[str, str]] = None

    async def get_discovery_document(self) -> Dict[str, str]:
        """
        Fetch and cache the OpenID Connect discovery document.

        Returns:
            Dictionary with endpoint URLs
        """
        if self._discovery_cache:
            return self._discovery_cache

        async with httpx.AsyncClient() as client:
            response = await client.get(self.provider.discovery_url)
            response.raise_for_status()
            self._discovery_cache = response.json()

        return self._discovery_cache

    async def get_endpoints(self) -> Dict[str, str]:
        """
        Get OAuth/OIDC endpoints.

        Returns discovery document endpoints or override values.
        """
        discovery = await self.get_discovery_document()

        return {
            "authorization": self.provider.authorization_endpoint or discovery.get("authorization_endpoint", ""),
            "token": self.provider.token_endpoint or discovery.get("token_endpoint", ""),
            "userinfo": self.provider.userinfo_endpoint or discovery.get("userinfo_endpoint", ""),
            "jwks": self.provider.jwks_uri or discovery.get("jwks_uri", ""),
        }

    def generate_state(self) -> str:
        """Generate a state parameter for CSRF protection."""
        return secrets.token_urlsafe(32)

    def generate_nonce(self) -> str:
        """Generate a nonce parameter for replay protection."""
        return secrets.token_urlsafe(32)

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str,
        nonce: Optional[str] = None,
    ) -> str:
        """
        Build the authorization URL.

        Args:
            redirect_uri: Callback URL after authorization
            state: CSRF protection state
            nonce: Replay protection nonce

        Returns:
            Full authorization URL
        """
        params = {
            "client_id": self.provider.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self.provider.scope,
            "state": state,
        }

        if nonce:
            params["nonce"] = nonce

        return f"{self.provider.authorization_endpoint}?{urlencode(params)}"

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from callback
            redirect_uri: Original redirect URI

        Returns:
            Token response dictionary
        """
        endpoints = await self.get_endpoints()

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.provider.client_id,
            "client_secret": self.provider.client_secret,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoints["token"],
                data=data,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    async def get_user_info(
        self,
        access_token: str,
    ) -> Dict[str, Any]:
        """
        Fetch user information using access token.

        Args:
            access_token: OAuth access token

        Returns:
            User info dictionary
        """
        endpoints = await self.get_endpoints()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                endpoints["userinfo"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()

    async def authenticate(
        self,
        code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """
        Complete OIDC authentication flow.

        Args:
            code: Authorization code from callback
            redirect_uri: Original redirect URI

        Returns:
            Dictionary with user information
        """
        # Exchange code for token
        token_response = await self.exchange_code_for_token(code, redirect_uri)
        access_token = token_response.get("access_token")

        if not access_token:
            raise ValueError("No access token in response")

        # Get user info
        user_info = await self.get_user_info(access_token)

        # Extract standard claims
        return {
            "provider_id": self.provider.provider_id,
            "provider_user_id": user_info.get("sub"),
            "email": user_info.get("email"),
            "name": user_info.get("name") or user_info.get("email", "").split("@")[0],
            "email_verified": user_info.get("email_verified", False),
            "picture": user_info.get("picture"),
            "locale": user_info.get("locale"),
            "raw": user_info,
        }
