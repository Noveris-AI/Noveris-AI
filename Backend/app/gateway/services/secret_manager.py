"""
Secret Manager Service.

This module provides encryption and decryption for sensitive credentials
stored in the gateway_secrets table.

Uses Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256).
"""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


class SecretManagerError(Exception):
    """Exception raised by SecretManager operations."""
    pass


class SecretManager:
    """
    Manages encryption and decryption of secrets.

    Secrets are encrypted using Fernet (AES-128-CBC with HMAC-SHA256).
    The encryption key is loaded from environment variable GATEWAY_SECRET_ENCRYPTION_KEY.

    Usage:
        manager = SecretManager()
        ciphertext = manager.encrypt("my-api-key")
        plaintext = manager.decrypt(ciphertext)
    """

    _instance: Optional["SecretManager"] = None
    ENV_KEY_NAME = "GATEWAY_SECRET_ENCRYPTION_KEY"

    def __new__(cls) -> "SecretManager":
        """Singleton pattern for secret manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the secret manager with encryption key."""
        if self._initialized:
            return

        key = os.environ.get(self.ENV_KEY_NAME)
        if not key:
            raise SecretManagerError(
                f"Missing encryption key. Set {self.ENV_KEY_NAME} environment variable."
            )

        # Validate and prepare key
        try:
            # Key can be provided as:
            # 1. Raw 32-byte key (will be base64 encoded)
            # 2. Base64-encoded 32-byte key
            # 3. Fernet-compatible key (already URL-safe base64 of 32 bytes)

            if len(key) == 32:
                # Raw 32-byte key, convert to Fernet format
                key = base64.urlsafe_b64encode(key.encode()).decode()
            elif len(key) == 44 and key.endswith("="):
                # Already Fernet-compatible (44 chars with padding)
                pass
            else:
                # Try to use as-is
                pass

            self._fernet = Fernet(key.encode())
            self._initialized = True
        except Exception as e:
            raise SecretManagerError(f"Invalid encryption key format: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The secret value to encrypt

        Returns:
            Base64-encoded ciphertext

        Raises:
            SecretManagerError: If encryption fails
        """
        try:
            ciphertext = self._fernet.encrypt(plaintext.encode())
            return ciphertext.decode()
        except Exception as e:
            raise SecretManagerError(f"Encryption failed: {e}")

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a ciphertext string.

        Args:
            ciphertext: Base64-encoded ciphertext

        Returns:
            Decrypted plaintext

        Raises:
            SecretManagerError: If decryption fails
        """
        try:
            plaintext = self._fernet.decrypt(ciphertext.encode())
            return plaintext.decode()
        except InvalidToken:
            raise SecretManagerError("Decryption failed: Invalid token or wrong key")
        except Exception as e:
            raise SecretManagerError(f"Decryption failed: {e}")

    @classmethod
    def generate_key(cls) -> str:
        """
        Generate a new Fernet-compatible encryption key.

        Returns:
            Base64-encoded 32-byte key suitable for GATEWAY_SECRET_ENCRYPTION_KEY
        """
        return Fernet.generate_key().decode()

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None


def get_secret_manager() -> SecretManager:
    """Get the singleton SecretManager instance."""
    return SecretManager()
