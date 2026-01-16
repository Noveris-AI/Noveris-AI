"""
Credential Encryption Service.

Provides secure encryption/decryption for sensitive credentials:
- SSH private keys
- Passwords
- BMC credentials

Uses AES-GCM with a master key from environment variables.
Supports key rotation and key versioning.
"""

import base64
import hashlib
import json
import os
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings


class CredentialEncryptionError(Exception):
    """Base exception for credential encryption errors."""
    pass


class KeyVersionMismatchError(CredentialEncryptionError):
    """Raised when trying to decrypt with wrong key version."""
    pass


class CredentialService:
    """
    Service for encrypting and decrypting sensitive credentials.

    Uses AES-256-GCM for authenticated encryption.
    The master key is derived from CREDENTIAL_MASTER_KEY environment variable.
    """

    # Algorithm identifier for versioning
    ALGORITHM_AES256_GCM = "AES256_GCM"
    ALGORITHM_AES256_CBC = "AES256_CBC"  # Legacy, not recommended

    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize the credential service.

        Args:
            master_key: Optional master key (for testing). Uses settings if None.
        """
        self._master_key = master_key or self._get_master_key()
        self._keys: Dict[int, bytes] = {}
        self._current_version = settings.credential.key_version

        # Derive encryption key from master key
        self._keys[self._current_version] = self._derive_key(self._master_key, self._current_version)

    def _get_master_key(self) -> str:
        """Get the master key from settings or environment."""
        key = settings.credential.master_key
        if not key or len(key) < 32:
            raise CredentialEncryptionError(
                "CREDENTIAL_MASTER_KEY must be at least 32 characters long"
            )
        return key

    def _derive_key(self, master_key: str, key_version: int) -> bytes:
        """
        Derive an encryption key from the master key using PBKDF2.

        Args:
            master_key: The master key string
            key_version: Version number for key rotation support

        Returns:
            32-byte encryption key
        """
        # Use PBKDF2 with HMAC-SHA256 to derive a key
        # Include version in salt for key rotation support
        salt = f"noveris-credential-{key_version}".encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(master_key.encode())

    def encrypt(self, payload: Dict[str, Any], key_version: Optional[int] = None) -> str:
        """
        Encrypt a credential payload.

        Args:
            payload: Dictionary containing sensitive data (e.g., {"password": "..."})
            key_version: Key version to use (defaults to current)

        Returns:
            Base64-encoded encrypted data with metadata

        Raises:
            CredentialEncryptionError: If encryption fails
        """
        if not payload:
            raise CredentialEncryptionError("Payload cannot be empty")

        key_version = key_version or self._current_version
        key = self._keys.get(key_version)
        if not key:
            raise CredentialEncryptionError(f"Key version {key_version} not available")

        try:
            # Convert payload to JSON
            plaintext = json.dumps(payload).encode('utf-8')

            # Generate random nonce/IV
            nonce = os.urandom(12)  # 96-bit nonce for GCM

            # Encrypt using AES-256-GCM
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)

            # Combine: nonce (12 bytes) + ciphertext + tag (16 bytes, included in ciphertext)
            # The cryptography library already appends the tag
            combined = nonce + ciphertext

            # Create metadata header
            header = json.dumps({
                "version": key_version,
                "algorithm": self.ALGORITHM_AES256_GCM,
                "nonce_len": len(nonce),
            }).encode('utf-8')

            # Format: header_len (4 bytes) + header + encrypted_data
            result = (
                len(header).to_bytes(4, 'big') +
                header +
                combined
            )

            # Return as base64 string
            return base64.b64encode(result).decode('utf-8')

        except Exception as e:
            raise CredentialEncryptionError(f"Encryption failed: {str(e)}") from e

    def decrypt(self, encrypted_data: str, key_version: Optional[int] = None) -> Dict[str, Any]:
        """
        Decrypt credential data.

        Args:
            encrypted_data: Base64-encoded encrypted data from encrypt()
            key_version: Expected key version (None to detect from data)

        Returns:
            Decrypted payload as dictionary

        Raises:
            CredentialEncryptionError: If decryption fails
            KeyVersionMismatchError: If key version doesn't match
        """
        if not encrypted_data:
            raise CredentialEncryptionError("Encrypted data cannot be empty")

        try:
            # Decode from base64
            data = base64.b64decode(encrypted_data.encode('utf-8'))

            # Extract header
            header_len = int.from_bytes(data[:4], 'big')
            header_data = data[4:4 + header_len]
            header = json.loads(header_data.decode('utf-8'))

            # Extract encrypted data
            encrypted = data[4 + header_len:]

            # Verify algorithm
            if header.get("algorithm") != self.ALGORITHM_AES256_GCM:
                raise CredentialEncryptionError(
                    f"Unsupported algorithm: {header.get('algorithm')}"
                )

            # Get key version
            data_key_version = header.get("version", 1)
            if key_version and key_version != data_key_version:
                raise KeyVersionMismatchError(
                    f"Key version mismatch: expected {key_version}, got {data_key_version}"
                )

            key = self._keys.get(data_key_version)
            if not key:
                # Try to derive legacy key if version 1
                if data_key_version == 1:
                    key = self._derive_key(self._master_key, 1)
                    self._keys[1] = key
                else:
                    raise KeyVersionMismatchError(
                        f"Cannot decrypt: key version {data_key_version} not available"
                    )

            # Extract nonce and ciphertext
            nonce_len = header.get("nonce_len", 12)
            nonce = encrypted[:nonce_len]
            ciphertext = encrypted[nonce_len:]

            # Decrypt using AES-256-GCM
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)

            # Parse JSON payload
            payload = json.loads(plaintext.decode('utf-8'))
            return payload

        except InvalidTag:
            raise CredentialEncryptionError(
                "Decryption failed: authentication tag mismatch (possible tampering)"
            ) from None
        except json.JSONDecodeError as e:
            raise CredentialEncryptionError(f"Invalid encrypted data format: {e}") from e
        except Exception as e:
            if isinstance(e, (CredentialEncryptionError, KeyVersionMismatchError)):
                raise
            raise CredentialEncryptionError(f"Decryption failed: {str(e)}") from e

    def encrypt_ssh_key(
        self,
        private_key: str,
        passphrase: Optional[str] = None,
        bastion_host: Optional[str] = None,
        bastion_user: Optional[str] = None,
        bastion_port: int = 22,
        bastion_key: Optional[str] = None,
        bastion_password: Optional[str] = None
    ) -> str:
        """
        Encrypt SSH credentials.

        Args:
            private_key: PEM-formatted private key
            passphrase: Optional passphrase for the key
            bastion_host: Optional bastion/jump host
            bastion_user: Username for bastion
            bastion_port: Port for bastion SSH
            bastion_key: Optional SSH key for bastion
            bastion_password: Optional password for bastion

        Returns:
            Encrypted credential string
        """
        payload = {
            "private_key": private_key,
            "passphrase": passphrase,
        }

        # Add bastion credentials if provided
        if bastion_host:
            payload["bastion"] = {
                "host": bastion_host,
                "user": bastion_user,
                "port": bastion_port,
                "auth": {}
            }
            if bastion_key:
                payload["bastion"]["auth"]["ssh_key"] = bastion_key
            if bastion_password:
                payload["bastion"]["auth"]["password"] = bastion_password

        return self.encrypt(payload)

    def decrypt_ssh_key(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt SSH credentials.

        Args:
            encrypted_data: Encrypted credential string

        Returns:
            Dictionary with keys: private_key, passphrase, bastion (optional)
        """
        return self.decrypt(encrypted_data)

    def encrypt_password(
        self,
        password: str,
        bastion_host: Optional[str] = None,
        bastion_user: Optional[str] = None,
        bastion_key: Optional[str] = None,
        bastion_password: Optional[str] = None
    ) -> str:
        """
        Encrypt password credentials.

        Args:
            password: The password
            bastion_host: Optional bastion host
            bastion_user: Username for bastion
            bastion_key: Optional SSH key for bastion
            bastion_password: Optional password for bastion

        Returns:
            Encrypted credential string
        """
        payload = {"password": password}

        if bastion_host:
            payload["bastion"] = {
                "host": bastion_host,
                "user": bastion_user,
                "auth": {}
            }
            if bastion_key:
                payload["bastion"]["auth"]["ssh_key"] = bastion_key
            if bastion_password:
                payload["bastion"]["auth"]["password"] = bastion_password

        return self.encrypt(payload)

    def decrypt_password(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt password credentials.

        Args:
            encrypted_data: Encrypted credential string

        Returns:
            Dictionary with keys: password, bastion (optional)
        """
        return self.decrypt(encrypted_data)

    def encrypt_bmc_credentials(self, bmc_host: str, bmc_user: str, password: str) -> str:
        """
        Encrypt BMC credentials.

        Args:
            bmc_host: BMC IP/hostname
            bmc_user: BMC username
            password: BMC password

        Returns:
            Encrypted credential string
        """
        payload = {
            "bmc_host": bmc_host,
            "bmc_user": bmc_user,
            "password": password
        }
        return self.encrypt(payload)

    def decrypt_bmc_credentials(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt BMC credentials.

        Args:
            encrypted_data: Encrypted credential string

        Returns:
            Dictionary with keys: bmc_host, bmc_user, password
        """
        return self.decrypt(encrypted_data)

    def encrypt_winrm_credentials(
        self,
        username: str,
        password: Optional[str] = None,
        transport: str = "ntlm",
        cert_pem: Optional[str] = None,
        cert_key_pem: Optional[str] = None,
        server_cert_validation: str = "validate",
        kerberos_realm: Optional[str] = None
    ) -> str:
        """
        Encrypt WinRM credentials.

        Args:
            username: Windows username (domain\\user or user@domain for Kerberos)
            password: Password for NTLM/Kerberos/Basic/CredSSP auth
            transport: WinRM transport (ntlm, kerberos, basic, certificate, credssp)
            cert_pem: Client certificate for certificate auth
            cert_key_pem: Client certificate key
            server_cert_validation: Server cert validation mode (validate/ignore)
            kerberos_realm: Kerberos realm for Kerberos auth

        Returns:
            Encrypted credential string
        """
        payload = {
            "type": "winrm",
            "username": username,
            "transport": transport,
            "server_cert_validation": server_cert_validation,
        }

        if password:
            payload["password"] = password

        if transport == "certificate":
            if cert_pem:
                payload["cert_pem"] = cert_pem
            if cert_key_pem:
                payload["cert_key_pem"] = cert_key_pem

        if transport == "kerberos" and kerberos_realm:
            payload["kerberos_realm"] = kerberos_realm

        return self.encrypt(payload)

    def decrypt_winrm_credentials(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt WinRM credentials.

        Args:
            encrypted_data: Encrypted credential string

        Returns:
            Dictionary with WinRM credential fields
        """
        return self.decrypt(encrypted_data)

    def hash_for_logging(self, encrypted_data: str) -> str:
        """
        Generate a safe hash of encrypted data for logging.

        This produces a hash that can be used in logs to track
        credentials without exposing sensitive data.

        Args:
            encrypted_data: Encrypted credential string

        Returns:
            SHA-256 hash (first 16 chars) for logging
        """
        return hashlib.sha256(encrypted_data.encode()).hexdigest()[:16]

    def rotate_key(self, old_encrypted: str, new_version: int) -> str:
        """
        Rotate credential to a new key version.

        Args:
            old_encrypted: Current encrypted credential
            new_version: New key version to use

        Returns:
            Re-encrypted credential with new key version
        """
        # Decrypt with old key
        payload = self.decrypt(old_encrypted)

        # Encrypt with new key
        return self.encrypt(payload, key_version=new_version)


# Singleton instance
_credential_service: Optional[CredentialService] = None


def get_credential_service() -> CredentialService:
    """Get the singleton credential service instance."""
    global _credential_service
    if _credential_service is None:
        _credential_service = CredentialService()
    return _credential_service


def reset_credential_service():
    """Reset the credential service (for testing)."""
    global _credential_service
    _credential_service = None
