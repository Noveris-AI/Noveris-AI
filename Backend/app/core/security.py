"""
Security utilities for password hashing, validation, and token generation.
"""

import secrets
import string
from typing import Optional

import bcrypt

from app.core.config import settings


class PasswordPolicy:
    """Password policy enforcement."""

    @staticmethod
    def validate(password: str) -> tuple[bool, list[str]]:
        """
        Validate password against policy requirements.

        Returns:
            Tuple of (is_valid, list_of_missing_requirements)
        """
        missing = []

        if len(password) < settings.password.min_length:
            missing.append(f"至少{settings.password.min_length}个字符")

        if len(password) > settings.password.max_length:
            missing.append(f"最多{settings.password.max_length}个字符")

        if settings.password.require_uppercase and not any(c.isupper() for c in password):
            missing.append("大写字母")

        if settings.password.require_lowercase and not any(c.islower() for c in password):
            missing.append("小写字母")

        if settings.password.require_digit and not any(c.isdigit() for c in password):
            missing.append("数字")

        if settings.password.require_special:
            special_chars = set(settings.password.special_chars)
            if not any(c in special_chars for c in password):
                missing.append("特殊字符")

        return len(missing) == 0, missing

    @staticmethod
    def hash(password: str) -> str:
        """Hash a password using bcrypt. Bcrypt has a 72 byte limit, so truncate if needed."""
        # Bcrypt can only handle 72 bytes
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        # Hash using bcrypt with 12 rounds (default for passlib bcrypt)
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash."""
        plain_bytes = plain_password.encode('utf-8')
        # Truncate to 72 bytes if needed for verification too
        if len(plain_bytes) > 72:
            plain_bytes = plain_bytes[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_bytes, hashed_bytes)

    @staticmethod
    def generate_temporary(length: int = 16) -> str:
        """Generate a temporary password."""
        chars = string.ascii_letters + string.digits + settings.password.special_chars
        return "".join(secrets.choice(chars) for _ in range(length))


class TokenGenerator:
    """Secure token generation utilities."""

    @staticmethod
    def generate_session_id() -> str:
        """Generate a secure session ID."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_csrf_token() -> str:
        """Generate a CSRF token."""
        return secrets.token_urlsafe(settings.csrf.token_length)

    @staticmethod
    def generate_reset_token() -> str:
        """Generate a password reset token."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_verification_code(length: Optional[int] = None) -> str:
        """Generate a numeric verification code."""
        code_length = length or settings.verify.verify_code_length
        return "".join(secrets.choice(string.digits) for _ in range(code_length))

    @staticmethod
    def generate_api_key() -> str:
        """Generate an API key."""
        return secrets.token_urlsafe(32)


class InputSanitizer:
    """Input sanitization utilities."""

    @staticmethod
    def sanitize_email(email: str) -> str:
        """Sanitize email input."""
        return email.strip().lower()

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Sanitize name input."""
        return name.strip()

    @staticmethod
    def sanitize_log_data(data: dict, sensitive_keys: Optional[set[str]] = None) -> dict:
        """
        Sanitize sensitive data from logs.

        Args:
            data: The data to sanitize
            sensitive_keys: Keys to redact (defaults to common sensitive keys)
        """
        if sensitive_keys is None:
            sensitive_keys = {
                "password",
                "token",
                "session_id",
                "secret",
                "key",
                "csrf_token",
                "access_token",
                "refresh_token",
                "api_key",
                "authorization",
            }

        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive_key in key_lower for sensitive_key in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = InputSanitizer.sanitize_log_data(value, sensitive_keys)
            elif isinstance(value, list):
                sanitized[key] = [
                    InputSanitizer.sanitize_log_data(item, sensitive_keys) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        return sanitized


def generate_random_string(length: int = 16) -> str:
    """Generate a random string for various purposes."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
