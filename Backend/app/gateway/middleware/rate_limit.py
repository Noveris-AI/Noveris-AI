"""
Rate Limiting Middleware.

This module provides Redis-based rate limiting for the AI Gateway.
Supports multiple rate limit types:
- Requests per minute/hour/day
- Tokens per minute/hour/day
- Per API key, per tenant, and global limits

Uses sliding window algorithm for accurate rate limiting.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

import redis.asyncio as redis


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: int  # Unix timestamp
    retry_after: Optional[int] = None  # Seconds until retry allowed
    reason: Optional[str] = None


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None
    tokens_per_minute: Optional[int] = None
    tokens_per_day: Optional[int] = None


class RateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.

    Keys are structured as:
        gateway:rl:{scope}:{identifier}:{window}:{bucket}

    Where:
        - scope: "key" | "tenant" | "global"
        - identifier: API key ID, tenant ID, or "global"
        - window: "rpm" | "rph" | "rpd" | "tpm" | "tpd"
        - bucket: Current time bucket (minute/hour/day)
    """

    # Window configurations (name, duration_seconds, bucket_size_seconds)
    WINDOWS = {
        "rpm": (60, 1),         # Requests per minute, 1-second buckets
        "rph": (3600, 60),      # Requests per hour, 1-minute buckets
        "rpd": (86400, 3600),   # Requests per day, 1-hour buckets
        "tpm": (60, 1),         # Tokens per minute, 1-second buckets
        "tpd": (86400, 3600),   # Tokens per day, 1-hour buckets
    }

    def __init__(self, redis_client: redis.Redis, key_prefix: str = "gateway:rl"):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self._lua_scripts: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize Lua scripts for atomic operations."""
        # Sliding window rate limit check script
        self._lua_scripts["check_and_increment"] = self.redis.register_script("""
            local key = KEYS[1]
            local limit = tonumber(ARGV[1])
            local window = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            local increment = tonumber(ARGV[4])

            -- Remove old entries
            redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)

            -- Get current count
            local current = redis.call('ZCARD', key)

            if current + increment > limit then
                -- Rate limit exceeded
                local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
                local reset_at = now + window
                if oldest[2] then
                    reset_at = tonumber(oldest[2]) + window
                end
                return {0, current, limit, reset_at}
            end

            -- Add new entries
            for i = 1, increment do
                redis.call('ZADD', key, now, now .. ':' .. i .. ':' .. math.random(1000000))
            end
            redis.call('EXPIRE', key, window + 1)

            return {1, current + increment, limit, now + window}
        """)

    async def check_rate_limit(
        self,
        api_key_id: UUID,
        tenant_id: UUID,
        config: RateLimitConfig,
        request_count: int = 1,
        token_count: int = 0
    ) -> RateLimitResult:
        """
        Check rate limits for a request.

        Checks in order:
        1. API key limits
        2. Tenant limits (if different from key limits)
        3. Global limits

        Returns the first limit that is exceeded, or allows the request.
        """
        now = int(time.time())

        # Check request limits
        if request_count > 0:
            # Requests per minute
            if config.requests_per_minute:
                result = await self._check_window(
                    scope="key",
                    identifier=str(api_key_id),
                    window_type="rpm",
                    limit=config.requests_per_minute,
                    increment=request_count,
                    now=now
                )
                if not result.allowed:
                    return result

            # Requests per hour
            if config.requests_per_hour:
                result = await self._check_window(
                    scope="key",
                    identifier=str(api_key_id),
                    window_type="rph",
                    limit=config.requests_per_hour,
                    increment=request_count,
                    now=now
                )
                if not result.allowed:
                    return result

            # Requests per day
            if config.requests_per_day:
                result = await self._check_window(
                    scope="key",
                    identifier=str(api_key_id),
                    window_type="rpd",
                    limit=config.requests_per_day,
                    increment=request_count,
                    now=now
                )
                if not result.allowed:
                    return result

        # Check token limits
        if token_count > 0:
            # Tokens per minute
            if config.tokens_per_minute:
                result = await self._check_window(
                    scope="key",
                    identifier=str(api_key_id),
                    window_type="tpm",
                    limit=config.tokens_per_minute,
                    increment=token_count,
                    now=now
                )
                if not result.allowed:
                    return result

            # Tokens per day
            if config.tokens_per_day:
                result = await self._check_window(
                    scope="key",
                    identifier=str(api_key_id),
                    window_type="tpd",
                    limit=config.tokens_per_day,
                    increment=token_count,
                    now=now
                )
                if not result.allowed:
                    return result

        # All limits passed
        return RateLimitResult(
            allowed=True,
            limit=0,
            remaining=0,
            reset_at=now + 60
        )

    async def _check_window(
        self,
        scope: str,
        identifier: str,
        window_type: str,
        limit: int,
        increment: int,
        now: int
    ) -> RateLimitResult:
        """Check a specific rate limit window."""
        window_duration, _ = self.WINDOWS[window_type]
        key = f"{self.key_prefix}:{scope}:{identifier}:{window_type}"

        # Use Lua script for atomic check-and-increment
        if "check_and_increment" in self._lua_scripts:
            result = await self._lua_scripts["check_and_increment"](
                keys=[key],
                args=[limit, window_duration, now, increment]
            )
            allowed, current, limit_val, reset_at = result
        else:
            # Fallback without Lua (less accurate but works)
            current = await self.redis.zcard(key)
            if current + increment > limit:
                allowed = 0
                reset_at = now + window_duration
            else:
                allowed = 1
                await self.redis.zadd(key, {f"{now}:{increment}": now})
                await self.redis.expire(key, window_duration + 1)
                reset_at = now + window_duration
            limit_val = limit

        if not allowed:
            retry_after = reset_at - now
            return RateLimitResult(
                allowed=False,
                limit=limit_val,
                remaining=0,
                reset_at=reset_at,
                retry_after=retry_after,
                reason=f"Rate limit exceeded for {window_type}"
            )

        return RateLimitResult(
            allowed=True,
            limit=limit_val,
            remaining=limit_val - current,
            reset_at=reset_at
        )

    async def record_tokens(
        self,
        api_key_id: UUID,
        prompt_tokens: int,
        completion_tokens: int
    ) -> None:
        """
        Record token usage after request completion.

        Called after streaming completes to record actual token usage.
        """
        now = int(time.time())
        total_tokens = prompt_tokens + completion_tokens

        if total_tokens > 0:
            # Update token per minute counter
            key_tpm = f"{self.key_prefix}:key:{api_key_id}:tpm"
            await self.redis.zadd(key_tpm, {f"{now}:{total_tokens}": now})
            await self.redis.expire(key_tpm, 61)

            # Update token per day counter
            key_tpd = f"{self.key_prefix}:key:{api_key_id}:tpd"
            await self.redis.zadd(key_tpd, {f"{now}:{total_tokens}": now})
            await self.redis.expire(key_tpd, 86401)

    async def get_current_usage(
        self,
        api_key_id: UUID
    ) -> Dict[str, int]:
        """Get current usage for all windows."""
        now = int(time.time())
        usage = {}

        for window_type, (duration, _) in self.WINDOWS.items():
            key = f"{self.key_prefix}:key:{api_key_id}:{window_type}"
            # Remove old entries
            await self.redis.zremrangebyscore(key, "-inf", now - duration)
            # Get current count
            count = await self.redis.zcard(key)
            usage[window_type] = count

        return usage


class QuotaManager:
    """
    Manages usage quotas for API keys.

    Quotas are persistent limits that reset on a schedule (daily, weekly, monthly).
    Unlike rate limits, quotas track cumulative usage over a period.
    """

    def __init__(self, redis_client: redis.Redis, key_prefix: str = "gateway:quota"):
        self.redis = redis_client
        self.key_prefix = key_prefix

    async def check_quota(
        self,
        api_key_id: UUID,
        quota_config: Dict[str, Any],
        tokens_to_use: int = 0,
        requests_to_use: int = 1
    ) -> RateLimitResult:
        """
        Check if request is within quota limits.

        Args:
            api_key_id: API key to check
            quota_config: Quota configuration from API key
            tokens_to_use: Estimated tokens for this request
            requests_to_use: Number of requests (usually 1)

        Returns:
            RateLimitResult indicating if request is allowed
        """
        if not quota_config:
            return RateLimitResult(allowed=True, limit=0, remaining=0, reset_at=0)

        max_tokens = quota_config.get("max_tokens", 0)
        max_requests = quota_config.get("max_requests", 0)
        reset_interval = quota_config.get("reset_interval", "monthly")

        # Get current period key
        period_key = self._get_period_key(reset_interval)
        key_base = f"{self.key_prefix}:{api_key_id}:{period_key}"

        # Check token quota
        if max_tokens > 0:
            token_key = f"{key_base}:tokens"
            current_tokens = int(await self.redis.get(token_key) or 0)

            if current_tokens + tokens_to_use > max_tokens:
                return RateLimitResult(
                    allowed=False,
                    limit=max_tokens,
                    remaining=max(0, max_tokens - current_tokens),
                    reset_at=self._get_period_reset_time(reset_interval),
                    reason="Token quota exceeded"
                )

        # Check request quota
        if max_requests > 0:
            request_key = f"{key_base}:requests"
            current_requests = int(await self.redis.get(request_key) or 0)

            if current_requests + requests_to_use > max_requests:
                return RateLimitResult(
                    allowed=False,
                    limit=max_requests,
                    remaining=max(0, max_requests - current_requests),
                    reset_at=self._get_period_reset_time(reset_interval),
                    reason="Request quota exceeded"
                )

        return RateLimitResult(
            allowed=True,
            limit=max_tokens or max_requests,
            remaining=max(0, (max_tokens - int(await self.redis.get(f"{key_base}:tokens") or 0))
                          if max_tokens else 0),
            reset_at=self._get_period_reset_time(reset_interval)
        )

    async def record_usage(
        self,
        api_key_id: UUID,
        quota_config: Dict[str, Any],
        tokens_used: int,
        requests_used: int = 1
    ) -> None:
        """Record usage against quota."""
        if not quota_config:
            return

        reset_interval = quota_config.get("reset_interval", "monthly")
        period_key = self._get_period_key(reset_interval)
        key_base = f"{self.key_prefix}:{api_key_id}:{period_key}"
        ttl = self._get_period_ttl(reset_interval)

        if tokens_used > 0:
            token_key = f"{key_base}:tokens"
            await self.redis.incrby(token_key, tokens_used)
            await self.redis.expire(token_key, ttl)

        if requests_used > 0:
            request_key = f"{key_base}:requests"
            await self.redis.incrby(request_key, requests_used)
            await self.redis.expire(request_key, ttl)

    def _get_period_key(self, interval: str) -> str:
        """Get current period identifier."""
        import datetime
        now = datetime.datetime.utcnow()

        if interval == "daily":
            return now.strftime("%Y-%m-%d")
        elif interval == "weekly":
            return now.strftime("%Y-W%W")
        elif interval == "monthly":
            return now.strftime("%Y-%m")
        else:
            return "forever"

    def _get_period_reset_time(self, interval: str) -> int:
        """Get Unix timestamp when current period resets."""
        import datetime
        now = datetime.datetime.utcnow()

        if interval == "daily":
            reset = (now + datetime.timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif interval == "weekly":
            days_until_monday = (7 - now.weekday()) % 7 or 7
            reset = (now + datetime.timedelta(days=days_until_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif interval == "monthly":
            if now.month == 12:
                reset = now.replace(year=now.year + 1, month=1, day=1,
                                    hour=0, minute=0, second=0, microsecond=0)
            else:
                reset = now.replace(month=now.month + 1, day=1,
                                    hour=0, minute=0, second=0, microsecond=0)
        else:
            reset = now + datetime.timedelta(days=365 * 10)  # Far future

        return int(reset.timestamp())

    def _get_period_ttl(self, interval: str) -> int:
        """Get TTL for current period keys."""
        if interval == "daily":
            return 86400 * 2  # 2 days
        elif interval == "weekly":
            return 86400 * 14  # 2 weeks
        elif interval == "monthly":
            return 86400 * 62  # ~2 months
        else:
            return 86400 * 365  # 1 year
