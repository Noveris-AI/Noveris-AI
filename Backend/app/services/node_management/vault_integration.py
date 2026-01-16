"""
HashiCorp Vault Integration Service.

Provides secure credential management using HashiCorp Vault:
- Store and retrieve SSH keys and passwords
- Automatic credential rotation
- Dynamic secrets for cloud providers
- Audit logging of credential access
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class VaultError(Exception):
    """Base exception for Vault operations."""
    pass


class VaultConnectionError(VaultError):
    """Failed to connect to Vault."""
    pass


class VaultAuthenticationError(VaultError):
    """Vault authentication failed."""
    pass


class VaultSecretNotFoundError(VaultError):
    """Secret not found in Vault."""
    pass


class VaultCredentialProvider(ABC):
    """Abstract base class for credential providers."""

    @abstractmethod
    async def get_credential(self, path: str) -> Dict[str, Any]:
        """Retrieve a credential from the provider."""
        pass

    @abstractmethod
    async def store_credential(
        self,
        path: str,
        credential: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store a credential in the provider."""
        pass

    @abstractmethod
    async def delete_credential(self, path: str) -> bool:
        """Delete a credential from the provider."""
        pass

    @abstractmethod
    async def rotate_credential(self, path: str) -> Dict[str, Any]:
        """Rotate a credential and return the new value."""
        pass


class HashiCorpVaultProvider(VaultCredentialProvider):
    """
    HashiCorp Vault credential provider.

    Supports:
    - KV v2 secrets engine for static credentials
    - SSH secrets engine for dynamic SSH keys
    - AWS/Azure/GCP secrets engine for cloud credentials
    - Transit engine for encryption
    """

    def __init__(
        self,
        vault_addr: str,
        token: Optional[str] = None,
        role_id: Optional[str] = None,
        secret_id: Optional[str] = None,
        namespace: Optional[str] = None,
        mount_point: str = "secret",
        verify_ssl: bool = True,
    ):
        self.vault_addr = vault_addr
        self.token = token
        self.role_id = role_id
        self.secret_id = secret_id
        self.namespace = namespace
        self.mount_point = mount_point
        self.verify_ssl = verify_ssl
        self._client = None
        self._token_expires_at: Optional[datetime] = None

    async def _get_client(self):
        """Get or create Vault client."""
        if self._client is None:
            try:
                import hvac
            except ImportError:
                raise VaultError("hvac library not installed. Run: pip install hvac")

            self._client = hvac.Client(
                url=self.vault_addr,
                token=self.token,
                namespace=self.namespace,
                verify=self.verify_ssl
            )

            # Authenticate if using AppRole
            if self.role_id and self.secret_id:
                await self._authenticate_approle()

            # Verify authentication
            if not self._client.is_authenticated():
                raise VaultAuthenticationError("Vault authentication failed")

        return self._client

    async def _authenticate_approle(self):
        """Authenticate using AppRole."""
        loop = asyncio.get_event_loop()

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._client.auth.approle.login(
                    role_id=self.role_id,
                    secret_id=self.secret_id
                )
            )

            self._client.token = response["auth"]["client_token"]

            # Track token expiration
            lease_duration = response["auth"].get("lease_duration", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=lease_duration)

            logger.info(
                "Vault AppRole authentication successful",
                lease_duration=lease_duration
            )

        except Exception as e:
            raise VaultAuthenticationError(f"AppRole authentication failed: {e}")

    async def _ensure_authenticated(self):
        """Ensure we have a valid token."""
        if self._token_expires_at and datetime.utcnow() >= self._token_expires_at:
            logger.info("Vault token expired, re-authenticating")
            self._client = None
            await self._get_client()

    async def get_credential(self, path: str) -> Dict[str, Any]:
        """
        Retrieve a credential from Vault KV store.

        Args:
            path: Path to the secret (without mount point prefix)

        Returns:
            Secret data as dictionary
        """
        await self._ensure_authenticated()
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=self.mount_point
                )
            )

            return response["data"]["data"]

        except Exception as e:
            if "secret not found" in str(e).lower():
                raise VaultSecretNotFoundError(f"Secret not found at {path}")
            raise VaultError(f"Failed to get credential: {e}")

    async def store_credential(
        self,
        path: str,
        credential: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store a credential in Vault KV store.

        Args:
            path: Path to store the secret
            credential: Secret data to store
            metadata: Optional custom metadata

        Returns:
            True if stored successfully
        """
        await self._ensure_authenticated()
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        try:
            # Add storage metadata
            credential_with_meta = {
                **credential,
                "_stored_at": datetime.utcnow().isoformat(),
                "_stored_by": "noveris-node-management"
            }

            await loop.run_in_executor(
                None,
                lambda: client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret=credential_with_meta,
                    mount_point=self.mount_point
                )
            )

            logger.info("Credential stored in Vault", path=path)
            return True

        except Exception as e:
            logger.error("Failed to store credential in Vault", path=path, error=str(e))
            raise VaultError(f"Failed to store credential: {e}")

    async def delete_credential(self, path: str) -> bool:
        """
        Delete a credential from Vault.

        Args:
            path: Path to the secret to delete

        Returns:
            True if deleted successfully
        """
        await self._ensure_authenticated()
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        try:
            # Permanently delete all versions
            await loop.run_in_executor(
                None,
                lambda: client.secrets.kv.v2.delete_metadata_and_all_versions(
                    path=path,
                    mount_point=self.mount_point
                )
            )

            logger.info("Credential deleted from Vault", path=path)
            return True

        except Exception as e:
            logger.error("Failed to delete credential from Vault", path=path, error=str(e))
            raise VaultError(f"Failed to delete credential: {e}")

    async def rotate_credential(self, path: str) -> Dict[str, Any]:
        """
        Rotate a credential (creates new version in Vault).

        This is a placeholder - actual rotation logic depends on credential type.
        For SSH keys, this would generate a new key pair.
        For passwords, this would generate a new random password.

        Args:
            path: Path to the credential

        Returns:
            New credential data
        """
        # Get current credential to determine type
        current = await self.get_credential(path)

        # Rotation depends on credential type
        if "private_key" in current:
            new_credential = await self._rotate_ssh_key(current)
        elif "password" in current:
            new_credential = await self._rotate_password(current)
        else:
            raise VaultError(f"Unknown credential type at {path}")

        # Store rotated credential
        await self.store_credential(path, new_credential)

        logger.info("Credential rotated", path=path)
        return new_credential

    async def _rotate_ssh_key(self, current: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a new SSH key pair."""
        import subprocess
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = os.path.join(tmpdir, "id_rsa")

            # Generate new key
            subprocess.run([
                "ssh-keygen",
                "-t", "rsa",
                "-b", "4096",
                "-f", key_path,
                "-N", "",  # No passphrase
                "-q"
            ], check=True)

            # Read keys
            with open(key_path, "r") as f:
                private_key = f.read()
            with open(f"{key_path}.pub", "r") as f:
                public_key = f.read()

        return {
            "private_key": private_key,
            "public_key": public_key,
            "rotated_at": datetime.utcnow().isoformat(),
            "previous_key_hash": self._hash_key(current.get("private_key", ""))
        }

    async def _rotate_password(self, current: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a new random password."""
        import secrets
        import string

        # Generate strong password
        alphabet = string.ascii_letters + string.digits + string.punctuation
        new_password = ''.join(secrets.choice(alphabet) for _ in range(32))

        return {
            "password": new_password,
            "rotated_at": datetime.utcnow().isoformat(),
            "username": current.get("username", "")
        }

    def _hash_key(self, key: str) -> str:
        """Create a hash of a key for audit purposes."""
        import hashlib
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    # Dynamic SSH Key Generation
    async def get_signed_ssh_key(
        self,
        role: str,
        public_key: str,
        valid_principals: Optional[List[str]] = None,
        ttl: str = "1h"
    ) -> Dict[str, str]:
        """
        Get a signed SSH certificate from Vault SSH secrets engine.

        Args:
            role: SSH role name in Vault
            public_key: Public key to sign
            valid_principals: List of valid principals (users/hosts)
            ttl: Certificate validity period

        Returns:
            Signed certificate and metadata
        """
        await self._ensure_authenticated()
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        try:
            params = {
                "public_key": public_key,
                "ttl": ttl,
            }
            if valid_principals:
                params["valid_principals"] = ",".join(valid_principals)

            response = await loop.run_in_executor(
                None,
                lambda: client.secrets.ssh.sign_ssh_key(
                    name=role,
                    **params
                )
            )

            return {
                "signed_key": response["data"]["signed_key"],
                "serial_number": response["data"]["serial_number"],
                "valid_until": response["data"].get("valid_until", "")
            }

        except Exception as e:
            raise VaultError(f"Failed to sign SSH key: {e}")

    # AWS Dynamic Credentials
    async def get_aws_credentials(
        self,
        role: str,
        ttl: str = "1h"
    ) -> Dict[str, str]:
        """
        Get dynamic AWS credentials from Vault AWS secrets engine.

        Args:
            role: AWS role name in Vault
            ttl: Credential validity period

        Returns:
            AWS access key ID, secret key, and session token
        """
        await self._ensure_authenticated()
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.secrets.aws.generate_credentials(
                    name=role,
                    ttl=ttl
                )
            )

            return {
                "access_key_id": response["data"]["access_key"],
                "secret_access_key": response["data"]["secret_key"],
                "security_token": response["data"].get("security_token"),
                "lease_id": response["lease_id"],
                "lease_duration": response["lease_duration"]
            }

        except Exception as e:
            raise VaultError(f"Failed to get AWS credentials: {e}")

    # Azure Dynamic Credentials
    async def get_azure_credentials(
        self,
        role: str,
        ttl: str = "1h"
    ) -> Dict[str, str]:
        """
        Get dynamic Azure credentials from Vault Azure secrets engine.

        Args:
            role: Azure role name in Vault
            ttl: Credential validity period

        Returns:
            Azure client ID, client secret, and tenant ID
        """
        await self._ensure_authenticated()
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.secrets.azure.generate_credentials(
                    name=role,
                    ttl=ttl
                )
            )

            return {
                "client_id": response["data"]["client_id"],
                "client_secret": response["data"]["client_secret"],
                "lease_id": response["lease_id"],
                "lease_duration": response["lease_duration"]
            }

        except Exception as e:
            raise VaultError(f"Failed to get Azure credentials: {e}")

    # Transit Encryption
    async def encrypt_data(
        self,
        key_name: str,
        plaintext: str
    ) -> str:
        """
        Encrypt data using Vault Transit engine.

        Args:
            key_name: Name of the encryption key in Vault
            plaintext: Data to encrypt (base64 encoded)

        Returns:
            Ciphertext
        """
        await self._ensure_authenticated()
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.secrets.transit.encrypt_data(
                    name=key_name,
                    plaintext=plaintext
                )
            )

            return response["data"]["ciphertext"]

        except Exception as e:
            raise VaultError(f"Transit encryption failed: {e}")

    async def decrypt_data(
        self,
        key_name: str,
        ciphertext: str
    ) -> str:
        """
        Decrypt data using Vault Transit engine.

        Args:
            key_name: Name of the encryption key in Vault
            ciphertext: Data to decrypt

        Returns:
            Plaintext (base64 encoded)
        """
        await self._ensure_authenticated()
        client = await self._get_client()
        loop = asyncio.get_event_loop()

        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.secrets.transit.decrypt_data(
                    name=key_name,
                    ciphertext=ciphertext
                )
            )

            return response["data"]["plaintext"]

        except Exception as e:
            raise VaultError(f"Transit decryption failed: {e}")


class VaultCredentialService:
    """
    High-level service for Vault credential management.

    Provides a tenant-aware interface for credential operations.
    """

    def __init__(self, vault_provider: VaultCredentialProvider):
        self.vault = vault_provider

    def _tenant_path(self, tenant_id: uuid.UUID, path: str) -> str:
        """Build tenant-scoped secret path."""
        return f"tenants/{tenant_id}/{path}"

    async def store_node_credential(
        self,
        tenant_id: uuid.UUID,
        node_id: uuid.UUID,
        credential_type: str,
        credential_data: Dict[str, Any]
    ) -> bool:
        """
        Store node credential in Vault.

        Args:
            tenant_id: Tenant UUID
            node_id: Node UUID
            credential_type: Type of credential (ssh_key, password, winrm)
            credential_data: Credential data to store

        Returns:
            True if stored successfully
        """
        path = self._tenant_path(
            tenant_id,
            f"nodes/{node_id}/credential"
        )

        data = {
            "type": credential_type,
            **credential_data,
            "node_id": str(node_id),
            "tenant_id": str(tenant_id)
        }

        return await self.vault.store_credential(path, data)

    async def get_node_credential(
        self,
        tenant_id: uuid.UUID,
        node_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Retrieve node credential from Vault.

        Args:
            tenant_id: Tenant UUID
            node_id: Node UUID

        Returns:
            Credential data
        """
        path = self._tenant_path(
            tenant_id,
            f"nodes/{node_id}/credential"
        )

        return await self.vault.get_credential(path)

    async def delete_node_credential(
        self,
        tenant_id: uuid.UUID,
        node_id: uuid.UUID
    ) -> bool:
        """
        Delete node credential from Vault.

        Args:
            tenant_id: Tenant UUID
            node_id: Node UUID

        Returns:
            True if deleted successfully
        """
        path = self._tenant_path(
            tenant_id,
            f"nodes/{node_id}/credential"
        )

        return await self.vault.delete_credential(path)

    async def rotate_node_credential(
        self,
        tenant_id: uuid.UUID,
        node_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Rotate node credential.

        Args:
            tenant_id: Tenant UUID
            node_id: Node UUID

        Returns:
            New credential data
        """
        path = self._tenant_path(
            tenant_id,
            f"nodes/{node_id}/credential"
        )

        return await self.vault.rotate_credential(path)

    async def get_cloud_credentials(
        self,
        tenant_id: uuid.UUID,
        provider: str,
        role: str
    ) -> Dict[str, Any]:
        """
        Get dynamic cloud credentials for a tenant.

        Args:
            tenant_id: Tenant UUID
            provider: Cloud provider (aws, azure, gcp)
            role: Vault role name

        Returns:
            Cloud credentials
        """
        if not isinstance(self.vault, HashiCorpVaultProvider):
            raise VaultError("Dynamic credentials require HashiCorp Vault")

        if provider == "aws":
            return await self.vault.get_aws_credentials(role)
        elif provider == "azure":
            return await self.vault.get_azure_credentials(role)
        else:
            raise VaultError(f"Unsupported cloud provider: {provider}")


# Factory function
def create_vault_service(
    vault_addr: Optional[str] = None,
    vault_token: Optional[str] = None,
    vault_role_id: Optional[str] = None,
    vault_secret_id: Optional[str] = None,
    namespace: Optional[str] = None,
) -> VaultCredentialService:
    """
    Create a Vault credential service.

    Args:
        vault_addr: Vault server address (defaults to settings)
        vault_token: Vault token for authentication
        vault_role_id: AppRole role ID
        vault_secret_id: AppRole secret ID
        namespace: Vault namespace

    Returns:
        VaultCredentialService instance
    """
    vault_addr = vault_addr or getattr(settings, 'vault_addr', None)
    if not vault_addr:
        raise VaultError("Vault address not configured")

    provider = HashiCorpVaultProvider(
        vault_addr=vault_addr,
        token=vault_token,
        role_id=vault_role_id,
        secret_id=vault_secret_id,
        namespace=namespace,
    )

    return VaultCredentialService(provider)
