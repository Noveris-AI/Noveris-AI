"""
Authentication service - business logic for user authentication.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import PasswordPolicy, TokenGenerator

logger = logging.getLogger(__name__)


# Compatibility for Python 3.9
UTC = timezone.utc
from app.models.user import User, UserLoginHistory, UserPasswordReset
from app.schemas.auth import UserResponse


class AuthService:
    """
    Authentication service handling user authentication operations.

    This service contains business logic for:
    - User registration and login
    - Password management
    - Verification codes
    - Login history tracking
    """

    def __init__(self, db: AsyncSession, redis):
        """
        Initialize auth service.

        Args:
            db: Database session
            redis: Redis client
        """
        self.db = db
        self.redis = redis
        self.password_policy = PasswordPolicy()
        self.token_gen = TokenGenerator()

    # ========================================================================
    # User Operations
    # ========================================================================

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            email: User email

        Returns:
            User or None
        """
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User or None
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        password: str,
        name: Optional[str] = None,
        is_verified: bool = False,
    ) -> User:
        """
        Create a new user.

        Args:
            email: User email
            password: Plain text password (will be hashed)
            name: Display name (defaults to email local part)
            is_verified: Whether email is already verified

        Returns:
            Created user
        """
        # Normalize email
        email = email.lower().strip()

        # Set default name
        if not name or not name.strip():
            name = email.split("@")[0]

        # Hash password
        password_hash = self.password_policy.hash(password)

        # Create user
        user = User(
            email=email,
            name=name,
            password_hash=password_hash,
            is_active=True,
            is_verified=is_verified,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def update_last_login(
        self,
        user: Optional[User],
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        sso_provider: Optional[str] = None,
    ) -> None:
        """
        Update user's last login timestamp and record login history.

        Args:
            user: User instance (can be None for failed attempts)
            success: Whether login was successful
            ip_address: Client IP address
            user_agent: Client user agent
            sso_provider: SSO provider if applicable
        """
        if success and user:
            user.last_login_at = datetime.now(UTC)

        # Record login history (only if we have a user_id)
        # For failed attempts with unknown user, we skip recording
        if user:
            history = UserLoginHistory(
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                sso_provider=sso_provider,
            )
            self.db.add(history)
            await self.db.commit()

    # ========================================================================
    # Authentication Operations
    # ========================================================================

    async def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> Optional[User]:
        """
        Authenticate user with email and password.

        Args:
            email: User email
            password: Plain text password

        Returns:
            User if authentication successful, None otherwise
        """
        user = await self.get_user_by_email(email)

        if not user:
            return None

        if not user.is_active:
            return None

        if not self.password_policy.verify(password, user.password_hash):
            return None

        return user

    async def verify_password(
        self,
        user: User,
        password: str,
    ) -> bool:
        """
        Verify password for a user.

        Args:
            user: User instance
            password: Plain text password

        Returns:
            True if password matches
        """
        return self.password_policy.verify(password, user.password_hash)

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> bool:
        """
        Change user password.

        Args:
            user: User instance
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            True if password changed successfully
        """
        # Verify current password
        if not self.password_policy.verify(current_password, user.password_hash):
            return False

        # Validate new password
        is_valid, missing = self.password_policy.validate(new_password)
        if not is_valid:
            raise ValueError(f"Password does not meet requirements: {', '.join(missing)}")

        # Hash and update
        user.password_hash = self.password_policy.hash(new_password)
        await self.db.commit()

        return True

    # ========================================================================
    # Verification Codes
    # ========================================================================

    async def create_verification_code(
        self,
        email: str,
        ttl: Optional[int] = None,
    ) -> str:
        """
        Create and store a verification code.

        Args:
            email: Email address
            ttl: Time to live in seconds (defaults to VERIFY_CODE_TTL)

        Returns:
            Verification code
        """
        code = self.token_gen.generate_verification_code()
        ttl = ttl or settings.verify.verify_code_ttl

        key = f"{settings.redis.verify_prefix}code:{email}"
        await self.redis.setex(key, ttl, code)

        # Log code in development
        if settings.verify.verify_dev_log_code:
            print(f"\n{'='*50}")
            print(f"Verification Code for {email}: {code}")
            print(f"{'='*50}\n")

        return code

    async def verify_code(
        self,
        email: str,
        code: str,
    ) -> bool:
        """
        Verify a code for an email.

        Args:
            email: Email address
            code: Verification code

        Returns:
            True if code is valid
        """
        key = f"{settings.redis.verify_prefix}code:{email}"
        stored_code = await self.redis.get(key)

        if not stored_code:
            return False

        if stored_code != code.strip():
            return False

        # Delete used code
        await self.redis.delete(key)

        return True

    async def consume_verification_code(
        self,
        email: str,
        code: str,
    ) -> bool:
        """
        Verify and consume a code (delete after use).

        Args:
            email: Email address
            code: Verification code

        Returns:
            True if code was valid and consumed
        """
        return await self.verify_code(email, code)

    # ========================================================================
    # Password Reset
    # ========================================================================

    async def create_password_reset(
        self,
        user: User,
    ) -> tuple[str, Optional[str]]:
        """
        Create a password reset token for a user.

        Args:
            user: User instance

        Returns:
            Tuple of (token, code) - code may be None based on settings
        """
        token = self.token_gen.generate_reset_token()
        code = None

        # Generate code if in code or both mode
        if settings.verify.reset_mode in ("code", "both"):
            code = self.token_gen.generate_verification_code()

        # Calculate expiration
        expires_at = datetime.now(UTC) + timedelta(seconds=settings.verify.reset_token_ttl)

        # Store in database
        reset = UserPasswordReset(
            user_id=user.id,
            token=token,
            code=code,
            expires_at=expires_at,
        )
        self.db.add(reset)
        await self.db.commit()

        # Log reset details in development for testing
        if settings.verify.verify_dev_log_code:
            print("=" * 50)
            print(f"Password Reset for {user.email}:")
            if token:
                print(f"  Token: {token}")
            if code:
                print(f"  Code: {code}")
            print("=" * 50)
            logger.info(f"Password reset created for {user.email}, token={token[:8]}..., code={code}")

        return token, code

    async def get_valid_password_reset(
        self,
        token: Optional[str] = None,
        code: Optional[str] = None,
    ) -> Optional[UserPasswordReset]:
        """
        Get a valid password reset record.

        Args:
            token: Reset token
            code: Reset code

        Returns:
            PasswordReset record or None
        """
        if not token and not code:
            return None

        query = select(UserPasswordReset).where(
            UserPasswordReset.used == False,
            UserPasswordReset.expires_at > datetime.now(UTC),
        )

        if token:
            query = query.where(UserPasswordReset.token == token)

        if code:
            query = query.where(UserPasswordReset.code == code)

        result = await self.db.execute(query.order_by(UserPasswordReset.created_at.desc()))
        return result.scalar_one_or_none()

    async def reset_password(
        self,
        reset: UserPasswordReset,
        new_password: str,
    ) -> bool:
        """
        Reset user password using a reset record.

        Args:
            reset: PasswordReset record
            new_password: New password

        Returns:
            True if password reset successfully
        """
        # Validate password
        is_valid, missing = self.password_policy.validate(new_password)
        if not is_valid:
            raise ValueError(f"Password does not meet requirements: {', '.join(missing)}")

        # Get user
        user = await self.get_user_by_id(reset.user_id)
        if not user:
            return False

        # Update password
        user.password_hash = self.password_policy.hash(new_password)

        # Mark reset as used
        reset.used = True
        reset.used_at = datetime.now(UTC)

        await self.db.commit()

        return True

    # ========================================================================
    # SSO User Creation
    # ========================================================================

    async def get_or_create_sso_user(
        self,
        provider: str,
        provider_id: str,
        email: str,
        name: Optional[str] = None,
    ) -> tuple[User, bool]:
        """
        Get or create a user from SSO provider.

        Args:
            provider: SSO provider name (google, azure, etc.)
            provider_id: Provider's user ID
            email: User email
            name: Display name

        Returns:
            Tuple of (user, is_newly_created)
        """
        # Try to find existing user by SSO provider
        result = await self.db.execute(
            select(User).where(
                User.sso_provider == provider,
                User.sso_provider_id == provider_id,
            )
        )
        user = result.scalar_one_or_none()

        if user:
            return user, False

        # Try to find by email (account linking)
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        user = result.scalar_one_or_none()

        if user:
            # Link SSO to existing account
            user.sso_provider = provider
            user.sso_provider_id = provider_id
            user.is_verified = True
            await self.db.commit()
            return user, False

        # Create new user
        user = User(
            email=email.lower(),
            name=name or email.split("@")[0],
            password_hash=self.password_policy.hash(self.token_gen.generate_api_key()),  # Random password
            is_active=True,
            is_verified=True,
            sso_provider=provider,
            sso_provider_id=provider_id,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user, True

    # ========================================================================
    # Validation
    # ========================================================================

    async def validate_registration_password(
        self,
        password: str,
    ) -> tuple[bool, list[str]]:
        """
        Validate password meets registration requirements.

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, list_of_missing_requirements)
        """
        return self.password_policy.validate(password)
