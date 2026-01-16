"""
Gateway Authentication Middleware.

This module handles API key authentication for the AI Gateway.
External clients use Bearer tokens to authenticate with the gateway.

Features:
- API key validation (bcrypt hash comparison)
- Key expiration checking
- Access control (allowed models/endpoints)
- Request context enrichment
"""

import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

import bcrypt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gateway import GatewayAPIKey, LogPayloadMode


@dataclass
class AuthContext:
    """Authentication context for a gateway request."""

    api_key_id: UUID
    tenant_id: UUID
    user_id: Optional[UUID]

    # Access control
    allowed_models: Set[str]
    allowed_endpoints: Set[str]

    # Rate limit config
    rate_limit: Dict[str, Any]
    quota: Dict[str, Any]

    # Logging policy
    log_payload_mode: LogPayloadMode

    # Raw key prefix for logging
    key_prefix: str


class AuthenticationError(Exception):
    """Exception raised when authentication fails."""

    def __init__(
        self,
        message: str,
        error_type: str = "authentication_error",
        status_code: int = 401
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.status_code = status_code

    def to_openai_error(self) -> Dict[str, Any]:
        """Convert to OpenAI error format."""
        return {
            "error": {
                "message": self.message,
                "type": self.error_type,
                "param": None,
                "code": "invalid_api_key" if self.status_code == 401 else "forbidden",
            }
        }


class APIKeyGenerator:
    """Generates and hashes API keys."""

    # Key format: sk-<prefix>-<random>
    PREFIX_LENGTH = 8
    SECRET_LENGTH = 32

    @classmethod
    def generate(cls) -> tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            Tuple of (full_key, prefix, hash)
            - full_key: The complete key to show to user once
            - prefix: The first part of the key (for display)
            - hash: Bcrypt hash to store in database
        """
        # Generate random components
        prefix = secrets.token_hex(cls.PREFIX_LENGTH // 2)
        secret = secrets.token_hex(cls.SECRET_LENGTH // 2)

        # Full key
        full_key = f"sk-{prefix}-{secret}"

        # Display prefix
        display_prefix = f"sk-{prefix}"

        # Hash for storage
        key_hash = bcrypt.hashpw(full_key.encode(), bcrypt.gensalt()).decode()

        return full_key, display_prefix, key_hash

    @classmethod
    def verify(cls, key: str, key_hash: str) -> bool:
        """Verify a key against its hash."""
        try:
            return bcrypt.checkpw(key.encode(), key_hash.encode())
        except Exception:
            return False

    @classmethod
    def get_prefix(cls, key: str) -> str:
        """Extract the prefix from a key for lookup."""
        # Format: sk-<prefix>-<secret>
        parts = key.split("-")
        if len(parts) >= 2:
            return f"sk-{parts[1]}"
        return ""


class GatewayAuthenticator:
    """
    Authenticates gateway requests using API keys.

    Performs:
    1. Key format validation
    2. Database lookup by prefix
    3. Hash verification
    4. Expiration checking
    5. Access control validation
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(
        self,
        authorization_header: Optional[str],
        endpoint: str,
        model: Optional[str] = None
    ) -> AuthContext:
        """
        Authenticate a request using the Authorization header.

        Args:
            authorization_header: The Authorization header value
            endpoint: The requested endpoint
            model: The requested model (if applicable)

        Returns:
            AuthContext with authentication details

        Raises:
            AuthenticationError: If authentication fails
        """
        # 1. Extract Bearer token
        api_key = self._extract_bearer_token(authorization_header)

        # 2. Get key prefix for lookup
        prefix = APIKeyGenerator.get_prefix(api_key)
        if not prefix:
            raise AuthenticationError(
                "Invalid API key format",
                status_code=401
            )

        # 3. Lookup key by prefix
        key_record = await self._lookup_key(prefix)
        if not key_record:
            raise AuthenticationError(
                "Invalid API key",
                status_code=401
            )

        # 4. Verify hash
        if not APIKeyGenerator.verify(api_key, key_record.key_hash):
            raise AuthenticationError(
                "Invalid API key",
                status_code=401
            )

        # 5. Check if enabled
        if not key_record.enabled:
            raise AuthenticationError(
                "API key is disabled",
                status_code=403
            )

        # 6. Check expiration
        if key_record.expires_at and key_record.expires_at < datetime.utcnow():
            raise AuthenticationError(
                "API key has expired",
                status_code=403
            )

        # 7. Check access control
        await self._check_access(key_record, endpoint, model)

        # 8. Update last used timestamp (async, non-blocking)
        await self._update_last_used(key_record.id)

        # Build auth context
        return AuthContext(
            api_key_id=key_record.id,
            tenant_id=key_record.tenant_id,
            user_id=key_record.user_id,
            allowed_models=set(key_record.allowed_models or []),
            allowed_endpoints=set(key_record.allowed_endpoints or []),
            rate_limit=key_record.rate_limit or {},
            quota=key_record.quota or {},
            log_payload_mode=key_record.log_payload_mode or LogPayloadMode.METADATA_ONLY,
            key_prefix=key_record.key_prefix
        )

    def _extract_bearer_token(self, authorization_header: Optional[str]) -> str:
        """Extract the Bearer token from Authorization header."""
        if not authorization_header:
            raise AuthenticationError(
                "Missing Authorization header",
                status_code=401
            )

        parts = authorization_header.split()
        if len(parts) != 2:
            raise AuthenticationError(
                "Invalid Authorization header format",
                status_code=401
            )

        scheme, token = parts
        if scheme.lower() != "bearer":
            raise AuthenticationError(
                "Invalid authentication scheme. Use 'Bearer <api_key>'",
                status_code=401
            )

        return token

    async def _lookup_key(self, prefix: str) -> Optional[GatewayAPIKey]:
        """Look up API key by prefix."""
        stmt = select(GatewayAPIKey).where(GatewayAPIKey.key_prefix == prefix)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _check_access(
        self,
        key_record: GatewayAPIKey,
        endpoint: str,
        model: Optional[str]
    ) -> None:
        """Check if the key has access to the endpoint and model."""
        # Check endpoint access
        allowed_endpoints = key_record.allowed_endpoints or []
        if allowed_endpoints:
            if not self._matches_pattern(endpoint, allowed_endpoints):
                raise AuthenticationError(
                    f"Access denied to endpoint: {endpoint}",
                    status_code=403
                )

        # Check model access
        if model:
            allowed_models = key_record.allowed_models or []
            if allowed_models:
                if not self._matches_pattern(model, allowed_models):
                    raise AuthenticationError(
                        f"Access denied to model: {model}",
                        status_code=403
                    )

    def _matches_pattern(self, value: str, patterns: List[str]) -> bool:
        """Check if value matches any pattern (supports wildcards)."""
        import fnmatch

        for pattern in patterns:
            if fnmatch.fnmatch(value, pattern):
                return True
        return False

    async def _update_last_used(self, key_id: UUID) -> None:
        """Update the last_used_at timestamp."""
        try:
            stmt = (
                update(GatewayAPIKey)
                .where(GatewayAPIKey.id == key_id)
                .values(last_used_at=datetime.utcnow())
            )
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception:
            # Non-critical, don't fail the request
            pass


class AccessControlChecker:
    """
    Additional access control checks beyond basic authentication.

    Checks:
    - Model capability requirements
    - Endpoint-specific restrictions
    - Request payload validation
    """

    @staticmethod
    def check_model_access(
        auth_ctx: AuthContext,
        virtual_model: str,
        endpoint: str
    ) -> None:
        """
        Check if the authenticated key can access the model.

        Args:
            auth_ctx: Authentication context
            virtual_model: The requested virtual model
            endpoint: The requested endpoint

        Raises:
            AuthenticationError: If access is denied
        """
        # If allowed_models is empty, all models are allowed
        if not auth_ctx.allowed_models:
            return

        # Check against allowed patterns
        import fnmatch
        for pattern in auth_ctx.allowed_models:
            if fnmatch.fnmatch(virtual_model, pattern):
                return

        raise AuthenticationError(
            f"Access denied to model: {virtual_model}",
            status_code=403
        )

    @staticmethod
    def check_endpoint_access(
        auth_ctx: AuthContext,
        endpoint: str
    ) -> None:
        """
        Check if the authenticated key can access the endpoint.

        Args:
            auth_ctx: Authentication context
            endpoint: The requested endpoint

        Raises:
            AuthenticationError: If access is denied
        """
        # If allowed_endpoints is empty, all endpoints are allowed
        if not auth_ctx.allowed_endpoints:
            return

        # Check against allowed patterns
        import fnmatch
        for pattern in auth_ctx.allowed_endpoints:
            if fnmatch.fnmatch(endpoint, pattern):
                return

        raise AuthenticationError(
            f"Access denied to endpoint: {endpoint}",
            status_code=403
        )
