"""
OAuth2 SSO implementation.

Standard OAuth2 flow for providers like GitHub.
"""

import secrets
from typing import Any, Dict
from urllib.parse import urlencode

import httpx

from app.sso.config import OAuth2Provider


class OAuth2Service:
    """Service for handling OAuth2 authentication flow."""

    def __init__(self, provider: OAuth2Provider):
        """
        Initialize OAuth2 service.

        Args:
            provider: OAuth2 provider configuration
        """
        self.provider = provider

    def generate_state(self) -> str:
        """Generate a state parameter for CSRF protection."""
        return secrets.token_urlsafe(32)

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str,
    ) -> str:
        """
        Build the authorization URL.

        Args:
            redirect_uri: Callback URL after authorization
            state: CSRF protection state

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

        return f"{self.provider.authorization_url}?{urlencode(params)}"

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
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.provider.client_id,
            "client_secret": self.provider.client_secret,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.provider.token_url,
                data=data,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()

            # Some providers return form-encoded, try JSON first
            try:
                return response.json()
            except Exception:
                # Parse form-encoded response
                return dict(form_data.split("=") for form_data in response.text.split("&"))

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
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.provider.user_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()

    async def authenticate(
        self,
        code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """
        Complete OAuth2 authentication flow.

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

        # Normalize response (provider-specific)
        return self._normalize_user_info(user_info)

    def _normalize_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize user info to standard format.

        Args:
            user_info: Raw user info from provider

        Returns:
            Normalized user info
        """
        # GitHub specific normalization
        if "login" in user_info:
            return {
                "provider_id": self.provider.provider_id,
                "provider_user_id": str(user_info.get("id")),
                "email": user_info.get("email"),
                "name": user_info.get("name") or user_info.get("login"),
                "email_verified": True,  # GitHub OAuth requires verified email
                "picture": user_info.get("avatar_url"),
                "raw": user_info,
            }

        # Generic normalization
        return {
            "provider_id": self.provider.provider_id,
            "provider_user_id": user_info.get("id") or user_info.get("sub"),
            "email": user_info.get("email"),
            "name": user_info.get("name") or user_info.get("username"),
            "email_verified": user_info.get("email_verified", True),
            "picture": user_info.get("picture") or user_info.get("avatar"),
            "raw": user_info,
        }
