"""
Rate limiting service using Redis.
"""

from typing import Optional

from app.core.config import settings


class RateLimitService:
    """
    Rate limiting service to prevent abuse.

    Uses Redis sliding window algorithm for rate limiting.
    """

    def __init__(self, redis):
        """
        Initialize rate limit service.

        Args:
            redis: Redis client
        """
        self.redis = redis

    def _get_key(self, identifier: str, action: str) -> str:
        """Get Redis key for rate limiting."""
        return f"{settings.redis.ratelimit_prefix}{action}:{identifier}"

    async def check_rate_limit(
        self,
        identifier: str,
        action: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
    ) -> tuple[bool, int, int]:
        """
        Check if request is within rate limit.

        Args:
            identifier: Unique identifier (IP, email, user_id, etc.)
            action: Action type (login, code_request, api_call, etc.)
            limit: Maximum requests allowed (uses default if None)
            window: Time window in seconds (uses default if None)

        Returns:
            Tuple of (is_allowed, current_count, reset_time)
        """
        limit = limit or settings.rate_limit.default
        window = window or settings.rate_limit.window

        key = self._get_key(identifier, action)
        current_time = int(__import__("time").time())
        window_start = current_time - window

        # Remove old entries
        await self.redis.zremrangebyscore(key, 0, window_start)

        # Count current requests
        current_count = await self.redis.zcard(key)

        # Check if limit exceeded
        is_allowed = current_count < limit

        # Add current request
        if is_allowed:
            await self.redis.zadd(key, {str(current_time): current_time})
            await self.redis.expire(key, window)

        # Calculate reset time
        reset_time = current_time + window

        return is_allowed, current_count, reset_time

    async def record_attempt(
        self,
        identifier: str,
        action: str,
    ) -> None:
        """
        Record an attempt (without checking limit).

        Args:
            identifier: Unique identifier
            action: Action type
        """
        key = self._get_key(identifier, action)
        current_time = int(__import__("time").time())

        await self.redis.zadd(key, {str(current_time): current_time})
        await self.redis.expire(key, settings.rate_limit.window)

    async def get_count(
        self,
        identifier: str,
        action: str,
    ) -> int:
        """
        Get current attempt count.

        Args:
            identifier: Unique identifier
            action: Action type

        Returns:
            Current count
        """
        key = self._get_key(identifier, action)
        window = settings.rate_limit.window
        current_time = int(__import__("time").time())
        window_start = current_time - window

        # Remove old entries
        await self.redis.zremrangebyscore(key, 0, window_start)

        return await self.redis.zcard(key)

    async def reset(
        self,
        identifier: str,
        action: str,
    ) -> None:
        """
        Reset rate limit for identifier.

        Args:
            identifier: Unique identifier
            action: Action type
        """
        key = self._get_key(identifier, action)
        await self.redis.delete(key)

    async def is_banned(
        self,
        identifier: str,
    ) -> bool:
        """
        Check if identifier is currently banned.

        Args:
            identifier: Unique identifier

        Returns:
            True if banned
        """
        key = f"{settings.redis.ratelimit_prefix}ban:{identifier}"
        return await self.redis.exists(key) > 0

    async def ban(
        self,
        identifier: str,
        duration: Optional[int] = None,
    ) -> None:
        """
        Ban an identifier for a duration.

        Args:
            identifier: Unique identifier
            duration: Ban duration in seconds
        """
        key = f"{settings.redis.ratelimit_prefix}ban:{identifier}"
        duration = duration or settings.rate_limit.ban_duration
        await self.redis.setex(key, duration, "1")

    async def unban(
        self,
        identifier: str,
    ) -> None:
        """
        Unban an identifier.

        Args:
            identifier: Unique identifier
        """
        key = f"{settings.redis.ratelimit_prefix}ban:{identifier}"
        await self.redis.delete(key)
