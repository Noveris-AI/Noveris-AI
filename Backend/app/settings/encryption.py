"""
Settings encryption utilities.

Implements secure encryption for sensitive settings using Fernet (AES-128-CBC with HMAC).
Supports key rotation via MultiFernet.

Security considerations:
- Key must be at least 32 bytes (256 bits) for deriving Fernet key
- All sensitive data is encrypted at rest
- Key rotation is supported without downtime
- Never log or expose encryption keys

Environment variables:
- SETTINGS_ENCRYPTION_KEY: Primary encryption key (required in production)
- SETTINGS_ENCRYPTION_KEY_PREVIOUS: Previous key for rotation (optional)
"""

import base64
import hashlib
import json
import os
import struct
import time
from typing import Any, Optional, Union

from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from app.core.config import settings as app_settings


class SettingsEncryptionError(Exception):
    """Base exception for settings encryption errors."""
    pass


class EncryptionKeyError(SettingsEncryptionError):
    """Raised when there's an issue with the encryption key."""
    pass


class DecryptionError(SettingsEncryptionError):
    """Raised when decryption fails."""
    pass


def _derive_fernet_key(master_key: str, salt: Optional[bytes] = None) -> bytes:
    """
    Derive a Fernet-compatible key from a master key.

    Uses PBKDF2 with SHA256 to derive a 32-byte key from the master key,
    then base64 encodes it to get a valid Fernet key.

    Args:
        master_key: The master encryption key (at least 32 characters)
        salt: Optional salt for key derivation (uses fixed salt if not provided)

    Returns:
        A base64-encoded 32-byte key suitable for Fernet
    """
    if len(master_key) < 32:
        raise EncryptionKeyError("Master key must be at least 32 characters")

    # Use a fixed salt derived from the master key itself for deterministic key derivation
    # This allows the same key to be used across restarts
    if salt is None:
        salt = hashlib.sha256(b"noveris-settings-salt").digest()[:16]

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend(),
    )

    derived_key = kdf.derive(master_key.encode())
    return base64.urlsafe_b64encode(derived_key)


class SettingsEncryption:
    """
    Handles encryption/decryption of sensitive settings values.

    Uses Fernet symmetric encryption with support for key rotation.
    """

    def __init__(
        self,
        primary_key: Optional[str] = None,
        previous_key: Optional[str] = None,
    ):
        """
        Initialize the encryption handler.

        Args:
            primary_key: Primary encryption key. If not provided, reads from env.
            previous_key: Previous encryption key for rotation. If not provided, reads from env.
        """
        # Get keys from parameters or environment
        self._primary_key = primary_key or os.getenv(
            "SETTINGS_ENCRYPTION_KEY",
            app_settings.credential.master_key,
        )
        self._previous_key = previous_key or os.getenv("SETTINGS_ENCRYPTION_KEY_PREVIOUS")

        # Validate primary key
        if not self._primary_key:
            raise EncryptionKeyError(
                "SETTINGS_ENCRYPTION_KEY or CREDENTIAL_MASTER_KEY must be set"
            )

        # Create Fernet instances
        self._fernet = self._create_fernet()

    def _create_fernet(self) -> Union[Fernet, MultiFernet]:
        """Create Fernet or MultiFernet instance with available keys."""
        try:
            primary_fernet_key = _derive_fernet_key(self._primary_key)
            primary_fernet = Fernet(primary_fernet_key)

            if self._previous_key:
                previous_fernet_key = _derive_fernet_key(self._previous_key)
                previous_fernet = Fernet(previous_fernet_key)
                # MultiFernet tries keys in order: primary first, then previous
                return MultiFernet([primary_fernet, previous_fernet])

            return primary_fernet

        except Exception as e:
            raise EncryptionKeyError(f"Failed to create Fernet instance: {e}")

    def encrypt(self, data: Any) -> bytes:
        """
        Encrypt data to bytes.

        Args:
            data: Data to encrypt. Can be str, dict, list, or any JSON-serializable type.

        Returns:
            Encrypted bytes
        """
        if data is None:
            raise SettingsEncryptionError("Cannot encrypt None value")

        try:
            # Serialize to JSON if not already a string
            if isinstance(data, str):
                plaintext = data.encode("utf-8")
            else:
                plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")

            return self._fernet.encrypt(plaintext)

        except Exception as e:
            raise SettingsEncryptionError(f"Encryption failed: {e}")

    def decrypt(self, encrypted_data: bytes) -> Any:
        """
        Decrypt bytes back to original data.

        Args:
            encrypted_data: Encrypted bytes

        Returns:
            Decrypted data (dict, list, or string depending on what was encrypted)
        """
        if encrypted_data is None:
            raise DecryptionError("Cannot decrypt None value")

        try:
            plaintext = self._fernet.decrypt(encrypted_data)
            decoded = plaintext.decode("utf-8")

            # Try to parse as JSON
            try:
                return json.loads(decoded)
            except json.JSONDecodeError:
                # Return as plain string if not valid JSON
                return decoded

        except InvalidToken:
            raise DecryptionError(
                "Decryption failed: Invalid token. "
                "The data may be corrupted or encrypted with a different key."
            )
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}")

    def decrypt_to_string(self, encrypted_data: bytes) -> str:
        """
        Decrypt bytes to string without JSON parsing.

        Args:
            encrypted_data: Encrypted bytes

        Returns:
            Decrypted string
        """
        if encrypted_data is None:
            raise DecryptionError("Cannot decrypt None value")

        try:
            plaintext = self._fernet.decrypt(encrypted_data)
            return plaintext.decode("utf-8")
        except InvalidToken:
            raise DecryptionError(
                "Decryption failed: Invalid token. "
                "The data may be corrupted or encrypted with a different key."
            )
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}")

    def rotate_encryption(self, encrypted_data: bytes) -> bytes:
        """
        Re-encrypt data with the primary key.

        This is useful when rotating keys - decrypt with old key, encrypt with new.
        When using MultiFernet, this automatically uses the primary key.

        Args:
            encrypted_data: Data encrypted with any valid key

        Returns:
            Data encrypted with the primary key
        """
        if isinstance(self._fernet, MultiFernet):
            return self._fernet.rotate(encrypted_data)
        else:
            # For single Fernet, decrypt and re-encrypt
            decrypted = self.decrypt(encrypted_data)
            return self.encrypt(decrypted)

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new encryption key.

        Returns:
            A 32-byte random key encoded as hex string (64 characters)
        """
        return os.urandom(32).hex()


# Global instance (initialized lazily)
_encryption_instance: Optional[SettingsEncryption] = None


def get_settings_encryption() -> SettingsEncryption:
    """Get or create the global settings encryption instance."""
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = SettingsEncryption()
    return _encryption_instance


def encrypt_sensitive_value(value: Any) -> bytes:
    """
    Convenience function to encrypt a sensitive value.

    Args:
        value: Value to encrypt

    Returns:
        Encrypted bytes
    """
    return get_settings_encryption().encrypt(value)


def decrypt_sensitive_value(encrypted_data: bytes) -> Any:
    """
    Convenience function to decrypt a sensitive value.

    Args:
        encrypted_data: Encrypted bytes

    Returns:
        Decrypted value
    """
    return get_settings_encryption().decrypt(encrypted_data)


def mask_sensitive_string(value: str, visible_chars: int = 4) -> str:
    """
    Mask a sensitive string for display/logging.

    Args:
        value: String to mask
        visible_chars: Number of characters to keep visible at the end

    Returns:
        Masked string like "****abcd"
    """
    if not value:
        return ""
    if len(value) <= visible_chars:
        return "*" * len(value)
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


# List of sensitive setting keys that should be encrypted
SENSITIVE_SETTING_KEYS = frozenset([
    # SSO secrets
    "sso.oidc.client_secret",
    "sso.oauth2.client_secret",
    "sso.saml.x509_cert",
    "sso.saml.private_key",

    # Notification secrets
    "notification.smtp.password",
    "notification.webhook.signing_secret",
    "notification.slack.bot_token",
    "notification.feishu.app_secret",
    "notification.wecom.secret",
    "notification.dingtalk.app_secret",

    # API keys
    "api.key",
    "api.secret",

    # Database credentials (if stored in settings)
    "db.password",

    # External service credentials
    "huggingface.token",
    "openai.api_key",
])


def is_sensitive_key(key: str) -> bool:
    """
    Check if a setting key contains sensitive data.

    Args:
        key: Setting key

    Returns:
        True if the key is sensitive and should be encrypted
    """
    key_lower = key.lower()

    # Check against known sensitive keys
    if key_lower in SENSITIVE_SETTING_KEYS:
        return True

    # Check for sensitive patterns
    sensitive_patterns = [
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "privatekey",
        "credential",
        "cert",
        "certificate",
    ]

    return any(pattern in key_lower for pattern in sensitive_patterns)


def redact_sensitive_fields(data: dict, keys_to_redact: Optional[set] = None) -> dict:
    """
    Redact sensitive fields in a dictionary for logging/audit.

    Args:
        data: Dictionary to redact
        keys_to_redact: Optional set of keys to redact. If None, uses pattern matching.

    Returns:
        Dictionary with sensitive values replaced with "[REDACTED]"
    """
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        if keys_to_redact and key in keys_to_redact:
            result[key] = "[REDACTED]"
        elif is_sensitive_key(key):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = redact_sensitive_fields(value, keys_to_redact)
        elif isinstance(value, list):
            result[key] = [
                redact_sensitive_fields(item, keys_to_redact)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            result[key] = value

    return result
