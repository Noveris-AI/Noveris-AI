"""
Session management using Redis for storage.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.core.config import settings
from app.core.security import TokenGenerator


# Compatibility for Python 3.9
UTC = timezone.utc


class SessionData:
    """Session data structure."""

    def __init__(
        self,
        user_id: str,
        email: str,
        name: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        remember_me: bool = False,
    ):
        self.user_id = user_id
        self.email = email
        self.name = name
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.remember_me = remember_me
        self.created_at = datetime.now(UTC)
        self.expires_at = self.created_at + timedelta(
            seconds=settings.session.remember_ttl if remember_me else settings.session.ttl
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert session data to dictionary."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "remember_me": self.remember_me,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionData":
        """Create session data from dictionary."""
        session = cls(
            user_id=data["user_id"],
            email=data["email"],
            name=data["name"],
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            remember_me=data.get("remember_me", False),
        )
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.expires_at = datetime.fromisoformat(data["expires_at"])
        return session

    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now(UTC) > self.expires_at

    def extend(self) -> None:
        """Extend session expiration."""
        ttl = settings.session.remember_ttl if self.remember_me else settings.session.ttl
        self.expires_at = datetime.now(UTC) + timedelta(seconds=ttl)


class SessionManager:
    """
    Session manager for handling user sessions.

    This class provides an interface for session operations.
    The actual Redis operations are handled through the Redis dependency.
    """

    def __init__(self, redis_client):
        """
        Initialize session manager.

        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client
        self.generator = TokenGenerator()

    def _get_session_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"{settings.redis.session_prefix}{session_id}"

    def _get_user_sessions_key(self, user_id: str) -> str:
        """Get Redis key for user's session list."""
        return f"{settings.redis.session_prefix}user:{user_id}"

    async def create(
        self,
        user_id: str,
        email: str,
        name: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        remember_me: bool = False,
    ) -> str:
        """
        Create a new session.

        Args:
            user_id: User ID
            email: User email
            name: User name
            ip_address: Client IP address
            user_agent: Client user agent
            remember_me: Whether to extend session duration

        Returns:
            Session ID
        """
        session_id = self.generator.generate_session_id()
        session = SessionData(
            user_id=user_id,
            email=email,
            name=name,
            ip_address=ip_address,
            user_agent=user_agent,
            remember_me=remember_me,
        )

        # Check and enforce max sessions per user
        await self._enforce_max_sessions(user_id)

        # Store session data
        session_key = self._get_session_key(session_id)
        ttl = settings.session.remember_ttl if remember_me else settings.session.ttl
        await self.redis.setex(session_key, ttl, json.dumps(session.to_dict()))

        # Add to user's session list
        user_sessions_key = self._get_user_sessions_key(user_id)
        await self.redis.sadd(user_sessions_key, session_id)
        await self.redis.expire(user_sessions_key, ttl)

        return session_id

    async def get(self, session_id: str) -> Optional[SessionData]:
        """
        Get session data.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if not found
        """
        session_key = self._get_session_key(session_id)
        data = await self.redis.get(session_key)

        if not data:
            return None

        session = SessionData.from_dict(json.loads(data))

        # Check if expired
        if session.is_expired():
            await self.destroy(session_id)
            return None

        return session

    async def extend(self, session_id: str) -> bool:
        """
        Extend session expiration.

        Args:
            session_id: Session ID

        Returns:
            True if extended, False if not found
        """
        session = await self.get(session_id)
        if not session:
            return False

        session.extend()
        session_key = self._get_session_key(session_id)
        ttl = settings.session.remember_ttl if session.remember_me else settings.session.ttl
        await self.redis.setex(session_key, ttl, json.dumps(session.to_dict()))

        # Also extend the user sessions key
        user_sessions_key = self._get_user_sessions_key(session.user_id)
        await self.redis.expire(user_sessions_key, ttl)

        return True

    async def destroy(self, session_id: str) -> bool:
        """
        Destroy a session.

        Args:
            session_id: Session ID

        Returns:
            True if destroyed, False if not found
        """
        session = await self.get(session_id)
        if not session:
            return False

        # Remove session data
        session_key = self._get_session_key(session_id)
        await self.redis.delete(session_key)

        # Remove from user's session list
        user_sessions_key = self._get_user_sessions_key(session.user_id)
        await self.redis.srem(user_sessions_key, session_id)

        return True

    async def destroy_all_for_user(self, user_id: str) -> int:
        """
        Destroy all sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of sessions destroyed
        """
        user_sessions_key = self._get_user_sessions_key(user_id)
        session_ids = await self.redis.smembers(user_sessions_key)

        if not session_ids:
            return 0

        # Delete all sessions
        count = 0
        for session_id in session_ids:
            session_key = self._get_session_key(session_id)
            await self.redis.delete(session_key)
            count += 1

        # Clear the user's session list
        await self.redis.delete(user_sessions_key)

        return count

    async def _enforce_max_sessions(self, user_id: str) -> None:
        """
        Enforce maximum sessions per user by removing oldest sessions.

        Args:
            user_id: User ID
        """
        user_sessions_key = self._get_user_sessions_key(user_id)
        session_ids = await self.redis.smembers(user_sessions_key)

        max_sessions = settings.session.max_sessions_per_user

        if len(session_ids) >= max_sessions:
            # Remove oldest sessions (FIFO)
            sessions_to_remove = len(session_ids) - max_sessions + 1
            for session_id in list(session_ids)[:sessions_to_remove]:
                await self.destroy(session_id)

    async def get_user_session_count(self, user_id: str) -> int:
        """
        Get number of active sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of active sessions
        """
        user_sessions_key = self._get_user_sessions_key(user_id)
        return await self.redis.scard(user_sessions_key)
