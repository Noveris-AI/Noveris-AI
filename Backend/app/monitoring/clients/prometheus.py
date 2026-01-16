"""
Prometheus Client for Noveris Monitoring.

This module provides a robust Prometheus HTTP API client with:
- Connection pooling and timeout management
- Circuit breaker pattern for fault tolerance
- Query result caching with Redis
- PromQL query helpers
- Multi-tenant label injection
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode, urljoin

import httpx
import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.

    Prevents cascading failures by stopping requests to a failing service
    and allowing periodic tests to check if it has recovered.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout_seconds: int = 60,
        half_open_max_requests: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_requests = half_open_max_requests

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_requests = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def can_execute(self) -> bool:
        """Check if a request can be executed."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if timeout has passed
                if self._last_failure_time and \
                   time.time() - self._last_failure_time >= self.timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_requests = 0
                    self._success_count = 0
                    logger.info("circuit_breaker_half_open", timeout=self.timeout_seconds)
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_requests < self.half_open_max_requests:
                    self._half_open_requests += 1
                    return True
                return False

            return False

    async def record_success(self) -> None:
        """Record a successful request."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("circuit_breaker_closed", success_count=self._success_count)
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Record a failed request."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("circuit_breaker_reopened", failure_count=self._failure_count)
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "circuit_breaker_opened",
                        failure_count=self._failure_count,
                        threshold=self.failure_threshold
                    )


class QueryResult(BaseModel):
    """Prometheus query result."""

    status: str
    data: Dict[str, Any]
    error: Optional[str] = None
    error_type: Optional[str] = None
    warnings: List[str] = []


class PrometheusClient:
    """
    Async Prometheus HTTP API client.

    Features:
    - Robust error handling with circuit breaker
    - Query caching with configurable TTL
    - Connection pooling
    - PromQL query helpers
    """

    def __init__(
        self,
        base_url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        cache_ttl_seconds: int = 30,
        redis_client: Optional[Any] = None,
        circuit_breaker_config: Optional[Dict[str, int]] = None,
    ):
        """
        Initialize Prometheus client.

        Args:
            base_url: Prometheus server URL
            auth_type: Authentication type (none, basic, bearer)
            auth_config: Authentication configuration
            timeout_seconds: Request timeout
            max_retries: Maximum retry attempts
            cache_ttl_seconds: Query cache TTL
            redis_client: Redis client for caching (optional)
            circuit_breaker_config: Circuit breaker settings
        """
        self.base_url = base_url.rstrip("/")
        self.auth_type = auth_type
        self.auth_config = auth_config or {}
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.cache_ttl_seconds = cache_ttl_seconds
        self.redis_client = redis_client

        # Initialize circuit breaker
        cb_config = circuit_breaker_config or {}
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=cb_config.get("failure_threshold", 5),
            success_threshold=cb_config.get("success_threshold", 3),
            timeout_seconds=cb_config.get("timeout_seconds", 60),
            half_open_max_requests=cb_config.get("half_open_max_requests", 3),
        )

        # HTTP client will be created on first use
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            # Build auth headers
            headers = {"Accept": "application/json"}
            auth = None

            if self.auth_type == "bearer" and "token" in self.auth_config:
                headers["Authorization"] = f"Bearer {self.auth_config['token']}"
            elif self.auth_type == "basic":
                auth = httpx.BasicAuth(
                    username=self.auth_config.get("username", ""),
                    password=self.auth_config.get("password", ""),
                )

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                auth=auth,
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=True,
            )

        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _cache_key(self, query: str, params: Dict[str, Any]) -> str:
        """Generate cache key for a query."""
        key_data = json.dumps({"query": query, "params": params}, sort_keys=True)
        return f"prom:query:{hashlib.md5(key_data.encode()).hexdigest()}"

    async def _get_cached(self, cache_key: str) -> Optional[QueryResult]:
        """Get cached query result."""
        if not self.redis_client:
            return None

        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return QueryResult(**data)
        except Exception as e:
            logger.warning("cache_get_error", error=str(e))

        return None

    async def _set_cached(self, cache_key: str, result: QueryResult) -> None:
        """Cache query result."""
        if not self.redis_client:
            return

        try:
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl_seconds,
                result.model_dump_json(),
            )
        except Exception as e:
            logger.warning("cache_set_error", error=str(e))

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> QueryResult:
        """
        Make an HTTP request to Prometheus.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: POST data
            use_cache: Whether to use caching

        Returns:
            QueryResult with response data
        """
        # Check circuit breaker
        if not await self.circuit_breaker.can_execute():
            return QueryResult(
                status="error",
                data={},
                error="Circuit breaker is open - Prometheus unavailable",
                error_type="circuit_breaker_open",
            )

        # Check cache for GET requests
        cache_key = ""
        if use_cache and method == "GET" and params:
            cache_key = self._cache_key(endpoint, params)
            cached = await self._get_cached(cache_key)
            if cached:
                return cached

        # Make request with retries
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_client()

                if method == "GET":
                    response = await client.get(endpoint, params=params)
                elif method == "POST":
                    response = await client.post(endpoint, data=data, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                result_data = response.json()

                result = QueryResult(
                    status=result_data.get("status", "error"),
                    data=result_data.get("data", {}),
                    error=result_data.get("error"),
                    error_type=result_data.get("errorType"),
                    warnings=result_data.get("warnings", []),
                )

                # Record success and cache result
                await self.circuit_breaker.record_success()
                if use_cache and cache_key and result.status == "success":
                    await self._set_cached(cache_key, result)

                return result

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    "prometheus_http_error",
                    status_code=e.response.status_code,
                    attempt=attempt + 1,
                )
                if e.response.status_code >= 500:
                    await self.circuit_breaker.record_failure()
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                        continue
                break

            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(
                    "prometheus_request_error",
                    error=str(e),
                    attempt=attempt + 1,
                )
                await self.circuit_breaker.record_failure()
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                break

        # All retries failed
        return QueryResult(
            status="error",
            data={},
            error=str(last_error) if last_error else "Unknown error",
            error_type="request_failed",
        )

    async def query(
        self,
        promql: str,
        time: Optional[datetime] = None,
        timeout: Optional[str] = None,
        use_cache: bool = True,
    ) -> QueryResult:
        """
        Execute an instant query.

        Args:
            promql: PromQL query expression
            time: Evaluation timestamp (default: now)
            timeout: Query timeout
            use_cache: Whether to cache results

        Returns:
            QueryResult with instant query data
        """
        params: Dict[str, Any] = {"query": promql}

        if time:
            params["time"] = time.isoformat()
        if timeout:
            params["timeout"] = timeout

        return await self._request("GET", "/api/v1/query", params=params, use_cache=use_cache)

    async def query_range(
        self,
        promql: str,
        start: datetime,
        end: datetime,
        step: str = "1m",
        timeout: Optional[str] = None,
        use_cache: bool = True,
    ) -> QueryResult:
        """
        Execute a range query.

        Args:
            promql: PromQL query expression
            start: Start timestamp
            end: End timestamp
            step: Query resolution step
            timeout: Query timeout
            use_cache: Whether to cache results

        Returns:
            QueryResult with range query data
        """
        params: Dict[str, Any] = {
            "query": promql,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "step": step,
        }

        if timeout:
            params["timeout"] = timeout

        return await self._request("GET", "/api/v1/query_range", params=params, use_cache=use_cache)

    async def get_labels(self, match: Optional[List[str]] = None) -> QueryResult:
        """Get all label names."""
        params = {}
        if match:
            params["match[]"] = match
        return await self._request("GET", "/api/v1/labels", params=params)

    async def get_label_values(
        self,
        label: str,
        match: Optional[List[str]] = None,
    ) -> QueryResult:
        """Get values for a specific label."""
        params = {}
        if match:
            params["match[]"] = match
        return await self._request("GET", f"/api/v1/label/{label}/values", params=params)

    async def get_series(
        self,
        match: List[str],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> QueryResult:
        """Get time series matching the selector."""
        params: Dict[str, Any] = {"match[]": match}
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()
        return await self._request("GET", "/api/v1/series", params=params)

    async def get_targets(self, state: Optional[str] = None) -> QueryResult:
        """Get scrape targets."""
        params = {}
        if state:
            params["state"] = state
        return await self._request("GET", "/api/v1/targets", params=params, use_cache=False)

    async def get_rules(self, type: Optional[str] = None) -> QueryResult:
        """Get alerting and recording rules."""
        params = {}
        if type:
            params["type"] = type
        return await self._request("GET", "/api/v1/rules", params=params, use_cache=False)

    async def get_alerts(self) -> QueryResult:
        """Get active alerts."""
        return await self._request("GET", "/api/v1/alerts", use_cache=False)

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check Prometheus server health.

        Returns:
            Tuple of (is_healthy, message)
        """
        try:
            result = await self.query("up", use_cache=False)
            if result.status == "success":
                return True, "Prometheus is healthy"
            return False, result.error or "Unknown error"
        except Exception as e:
            return False, str(e)

    # ==========================================================================
    # Query Helpers
    # ==========================================================================

    def build_label_selector(self, labels: Dict[str, str]) -> str:
        """
        Build a label selector string.

        Args:
            labels: Label key-value pairs

        Returns:
            Label selector string like {job="node", instance="localhost:9100"}
        """
        if not labels:
            return ""

        parts = []
        for key, value in labels.items():
            # Escape special characters in value
            escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{key}="{escaped_value}"')

        return "{" + ", ".join(parts) + "}"

    def inject_tenant_label(self, promql: str, tenant_id: str) -> str:
        """
        Inject tenant label into a PromQL query for multi-tenancy.

        This is a simple implementation that adds the tenant filter.
        For production, consider using Prometheus remote-write with
        tenant isolation at the storage level.

        Args:
            promql: Original PromQL query
            tenant_id: Tenant ID to filter by

        Returns:
            Modified PromQL with tenant filter
        """
        # This is a simplified implementation
        # In production, you might want to use a proper PromQL parser
        tenant_filter = f'tenant_id="{tenant_id}"'

        # If query has existing selectors, add to them
        if "{" in promql:
            return promql.replace("{", "{" + tenant_filter + ", ", 1)
        else:
            # Find the metric name and add selector
            # This handles simple cases like "up" -> "up{tenant_id="xyz"}"
            parts = promql.split("(", 1)
            if len(parts) > 1:
                return f"{parts[0]}{{{tenant_filter}}}({parts[1]}"
            return f"{promql}{{{tenant_filter}}}"

    async def get_metric_value(
        self,
        metric: str,
        labels: Optional[Dict[str, str]] = None,
        aggregation: Optional[str] = None,
    ) -> Optional[float]:
        """
        Get a single metric value.

        Args:
            metric: Metric name
            labels: Label selectors
            aggregation: Aggregation function (sum, avg, max, min, count)

        Returns:
            Metric value or None if not found
        """
        selector = self.build_label_selector(labels or {})
        query = f"{metric}{selector}"

        if aggregation:
            query = f"{aggregation}({query})"

        result = await self.query(query)

        if result.status == "success" and result.data.get("result"):
            try:
                return float(result.data["result"][0]["value"][1])
            except (IndexError, KeyError, ValueError):
                pass

        return None

    async def get_histogram_percentile(
        self,
        metric: str,
        percentile: float,
        labels: Optional[Dict[str, str]] = None,
        range_duration: str = "5m",
    ) -> Optional[float]:
        """
        Calculate percentile from histogram metric.

        Args:
            metric: Histogram metric name (without _bucket suffix)
            percentile: Percentile value (0-1, e.g., 0.95 for P95)
            labels: Label selectors
            range_duration: Range vector duration

        Returns:
            Percentile value or None if not found
        """
        selector = self.build_label_selector(labels or {})
        query = f'histogram_quantile({percentile}, rate({metric}_bucket{selector}[{range_duration}]))'

        result = await self.query(query)

        if result.status == "success" and result.data.get("result"):
            try:
                return float(result.data["result"][0]["value"][1])
            except (IndexError, KeyError, ValueError):
                pass

        return None
