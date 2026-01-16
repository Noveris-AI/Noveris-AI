"""
Loki Client for Noveris Monitoring.

This module provides a Grafana Loki HTTP API client for log aggregation:
- Log query with LogQL
- Label and stream discovery
- Log line parsing and filtering
- Multi-tenant support
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from pydantic import BaseModel

from app.monitoring.clients.prometheus import CircuitBreaker, CircuitState

logger = structlog.get_logger(__name__)


class LogEntry(BaseModel):
    """Single log entry."""

    timestamp: int  # Nanoseconds since epoch
    line: str
    labels: Dict[str, str] = {}


class LogStream(BaseModel):
    """Log stream with entries."""

    stream: Dict[str, str]
    values: List[Tuple[str, str]]  # [(timestamp_ns, line), ...]


class LogQueryResult(BaseModel):
    """Loki query result."""

    status: str
    data: Dict[str, Any] = {}
    error: Optional[str] = None


class LokiClient:
    """
    Async Grafana Loki HTTP API client.

    Features:
    - LogQL query support
    - Label and stream discovery
    - Circuit breaker for fault tolerance
    - Multi-tenant label injection
    """

    def __init__(
        self,
        base_url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        default_limit: int = 1000,
        circuit_breaker_config: Optional[Dict[str, int]] = None,
    ):
        """
        Initialize Loki client.

        Args:
            base_url: Loki server URL
            auth_type: Authentication type (none, basic, bearer)
            auth_config: Authentication configuration
            timeout_seconds: Request timeout
            max_retries: Maximum retry attempts
            default_limit: Default log line limit
            circuit_breaker_config: Circuit breaker settings
        """
        self.base_url = base_url.rstrip("/")
        self.auth_type = auth_type
        self.auth_config = auth_config or {}
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.default_limit = default_limit

        # Initialize circuit breaker
        cb_config = circuit_breaker_config or {}
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=cb_config.get("failure_threshold", 5),
            success_threshold=cb_config.get("success_threshold", 3),
            timeout_seconds=cb_config.get("timeout_seconds", 60),
            half_open_max_requests=cb_config.get("half_open_max_requests", 3),
        )

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"Accept": "application/json"}
            auth = None

            if self.auth_type == "bearer" and "token" in self.auth_config:
                headers["Authorization"] = f"Bearer {self.auth_config['token']}"
            elif self.auth_type == "basic":
                auth = httpx.BasicAuth(
                    username=self.auth_config.get("username", ""),
                    password=self.auth_config.get("password", ""),
                )

            # Add X-Scope-OrgID header for multi-tenant Loki
            if "org_id" in self.auth_config:
                headers["X-Scope-OrgID"] = self.auth_config["org_id"]

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

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> LogQueryResult:
        """Make an HTTP request to Loki."""
        # Check circuit breaker
        if not await self.circuit_breaker.can_execute():
            return LogQueryResult(
                status="error",
                error="Circuit breaker is open - Loki unavailable",
            )

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_client()

                if method == "GET":
                    response = await client.get(endpoint, params=params)
                else:
                    response = await client.post(endpoint, json=params)

                response.raise_for_status()
                result_data = response.json()

                await self.circuit_breaker.record_success()

                return LogQueryResult(
                    status=result_data.get("status", "success"),
                    data=result_data.get("data", result_data),
                    error=result_data.get("error"),
                )

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    "loki_http_error",
                    status_code=e.response.status_code,
                    attempt=attempt + 1,
                )
                if e.response.status_code >= 500:
                    await self.circuit_breaker.record_failure()
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                break

            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(
                    "loki_request_error",
                    error=str(e),
                    attempt=attempt + 1,
                )
                await self.circuit_breaker.record_failure()
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                break

        return LogQueryResult(
            status="error",
            error=str(last_error) if last_error else "Unknown error",
        )

    @staticmethod
    def _datetime_to_ns(dt: datetime) -> int:
        """Convert datetime to nanoseconds since epoch."""
        return int(dt.timestamp() * 1_000_000_000)

    async def query(
        self,
        logql: str,
        limit: Optional[int] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        direction: str = "backward",
    ) -> LogQueryResult:
        """
        Execute a log query.

        Args:
            logql: LogQL query expression
            limit: Maximum number of entries
            start: Start timestamp
            end: End timestamp
            direction: Query direction (forward, backward)

        Returns:
            LogQueryResult with log data
        """
        params: Dict[str, Any] = {
            "query": logql,
            "limit": limit or self.default_limit,
            "direction": direction,
        }

        if start:
            params["start"] = self._datetime_to_ns(start)
        if end:
            params["end"] = self._datetime_to_ns(end)

        return await self._request("GET", "/loki/api/v1/query", params=params)

    async def query_range(
        self,
        logql: str,
        start: datetime,
        end: datetime,
        limit: Optional[int] = None,
        step: Optional[str] = None,
        direction: str = "backward",
    ) -> LogQueryResult:
        """
        Execute a range query.

        Args:
            logql: LogQL query expression
            start: Start timestamp
            end: End timestamp
            limit: Maximum number of entries
            step: Query resolution step
            direction: Query direction

        Returns:
            LogQueryResult with range data
        """
        params: Dict[str, Any] = {
            "query": logql,
            "start": self._datetime_to_ns(start),
            "end": self._datetime_to_ns(end),
            "limit": limit or self.default_limit,
            "direction": direction,
        }

        if step:
            params["step"] = step

        return await self._request("GET", "/loki/api/v1/query_range", params=params)

    async def get_labels(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> LogQueryResult:
        """Get all label names."""
        params = {}
        if start:
            params["start"] = self._datetime_to_ns(start)
        if end:
            params["end"] = self._datetime_to_ns(end)

        return await self._request("GET", "/loki/api/v1/labels", params=params)

    async def get_label_values(
        self,
        label: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> LogQueryResult:
        """Get values for a specific label."""
        params = {}
        if start:
            params["start"] = self._datetime_to_ns(start)
        if end:
            params["end"] = self._datetime_to_ns(end)

        return await self._request("GET", f"/loki/api/v1/label/{label}/values", params=params)

    async def get_series(
        self,
        match: List[str],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> LogQueryResult:
        """Get log streams matching selectors."""
        params: Dict[str, Any] = {"match[]": match}
        if start:
            params["start"] = self._datetime_to_ns(start)
        if end:
            params["end"] = self._datetime_to_ns(end)

        return await self._request("GET", "/loki/api/v1/series", params=params)

    async def tail(
        self,
        logql: str,
        delay_for: int = 0,
        limit: int = 100,
    ) -> LogQueryResult:
        """
        Tail logs in real-time.

        Note: This is a simplified implementation. For production WebSocket
        tailing, use the /loki/api/v1/tail endpoint with WebSocket client.

        Args:
            logql: LogQL query expression
            delay_for: Delay in seconds before starting
            limit: Maximum entries per poll

        Returns:
            LogQueryResult with recent logs
        """
        params = {
            "query": logql,
            "delay_for": delay_for,
            "limit": limit,
        }

        return await self._request("GET", "/loki/api/v1/tail", params=params)

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check Loki server health.

        Returns:
            Tuple of (is_healthy, message)
        """
        try:
            client = await self._get_client()
            response = await client.get("/ready")

            if response.status_code == 200:
                return True, "Loki is healthy"
            return False, f"Loki not ready: {response.status_code}"

        except Exception as e:
            return False, str(e)

    # ==========================================================================
    # Query Helpers
    # ==========================================================================

    def build_label_selector(self, labels: Dict[str, str]) -> str:
        """
        Build a LogQL label selector.

        Args:
            labels: Label key-value pairs

        Returns:
            Label selector string
        """
        if not labels:
            return "{}"

        parts = []
        for key, value in labels.items():
            escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{key}="{escaped_value}"')

        return "{" + ", ".join(parts) + "}"

    def inject_tenant_label(self, logql: str, tenant_id: str) -> str:
        """
        Inject tenant label into a LogQL query.

        Args:
            logql: Original LogQL query
            tenant_id: Tenant ID to filter by

        Returns:
            Modified LogQL with tenant filter
        """
        tenant_filter = f'tenant_id="{tenant_id}"'

        if "{" in logql:
            # Add to existing selector
            return logql.replace("{", "{" + tenant_filter + ", ", 1)
        else:
            # Query starts with stream selector
            return "{" + tenant_filter + "}" + logql

    async def search_logs(
        self,
        labels: Dict[str, str],
        search_text: Optional[str] = None,
        regex_pattern: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> LogQueryResult:
        """
        Search logs with text or regex filtering.

        Args:
            labels: Label selectors
            search_text: Plain text to search
            regex_pattern: Regex pattern to match
            start: Start timestamp
            end: End timestamp
            limit: Maximum entries

        Returns:
            LogQueryResult with matching logs
        """
        selector = self.build_label_selector(labels)
        logql = selector

        if search_text:
            # Line contains filter
            escaped_text = search_text.replace("`", "\\`")
            logql += f' |= `{escaped_text}`'
        elif regex_pattern:
            # Regex filter
            escaped_pattern = regex_pattern.replace("`", "\\`")
            logql += f' |~ `{escaped_pattern}`'

        return await self.query(logql, limit=limit, start=start, end=end)

    async def count_logs(
        self,
        labels: Dict[str, str],
        start: datetime,
        end: datetime,
        step: str = "1m",
    ) -> LogQueryResult:
        """
        Count log entries over time.

        Args:
            labels: Label selectors
            start: Start timestamp
            end: End timestamp
            step: Count interval

        Returns:
            LogQueryResult with count data
        """
        selector = self.build_label_selector(labels)
        logql = f"count_over_time({selector}[{step}])"

        return await self.query_range(logql, start=start, end=end, step=step)

    async def get_ssh_login_failures(
        self,
        node_labels: Optional[Dict[str, str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> LogQueryResult:
        """
        Get SSH login failure logs.

        Args:
            node_labels: Additional node label filters
            start: Start timestamp
            end: End timestamp
            limit: Maximum entries

        Returns:
            LogQueryResult with SSH failure logs
        """
        labels = {"job": "syslog"}
        if node_labels:
            labels.update(node_labels)

        # Common SSH failure patterns
        selector = self.build_label_selector(labels)
        logql = f'{selector} |~ "(?i)(failed|invalid|refused|authentication failure|not allowed)"'

        return await self.query(logql, limit=limit, start=start, end=end)

    async def aggregate_by_field(
        self,
        labels: Dict[str, str],
        json_field: str,
        start: datetime,
        end: datetime,
        step: str = "5m",
    ) -> LogQueryResult:
        """
        Aggregate log counts by a JSON field.

        Args:
            labels: Label selectors
            json_field: JSON field to group by
            start: Start timestamp
            end: End timestamp
            step: Aggregation interval

        Returns:
            LogQueryResult with aggregated counts
        """
        selector = self.build_label_selector(labels)
        # Parse JSON and sum by field
        logql = f'sum by ({json_field}) (count_over_time({selector} | json | {json_field} != "" [{step}]))'

        return await self.query_range(logql, start=start, end=end, step=step)
