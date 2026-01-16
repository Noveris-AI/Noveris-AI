"""
Alertmanager Client for Noveris Monitoring.

This module provides a Prometheus Alertmanager HTTP API client:
- Active alerts retrieval
- Alert silencing
- Alert acknowledgment tracking
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from pydantic import BaseModel

from app.monitoring.clients.prometheus import CircuitBreaker

logger = structlog.get_logger(__name__)


class AlertStatus(BaseModel):
    """Alert status information."""

    state: str  # active, suppressed, unprocessed
    silenced_by: List[str] = []
    inhibited_by: List[str] = []


class Alert(BaseModel):
    """Alert from Alertmanager."""

    fingerprint: str
    labels: Dict[str, str] = {}
    annotations: Dict[str, str] = {}
    starts_at: str
    ends_at: str
    updated_at: str
    status: AlertStatus
    receivers: List[Dict[str, str]] = []
    generator_url: Optional[str] = None


class Silence(BaseModel):
    """Alert silence."""

    id: str
    matchers: List[Dict[str, Any]]
    starts_at: str
    ends_at: str
    created_by: str
    comment: str
    status: Dict[str, str]


class AlertmanagerResult(BaseModel):
    """Alertmanager API result."""

    status: str
    data: Any = None
    error: Optional[str] = None


class AlertmanagerClient:
    """
    Async Prometheus Alertmanager HTTP API client.

    Features:
    - Alert retrieval and filtering
    - Silence management
    - Circuit breaker for fault tolerance
    """

    def __init__(
        self,
        base_url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        circuit_breaker_config: Optional[Dict[str, int]] = None,
    ):
        """
        Initialize Alertmanager client.

        Args:
            base_url: Alertmanager server URL
            auth_type: Authentication type
            auth_config: Authentication configuration
            timeout_seconds: Request timeout
            max_retries: Maximum retry attempts
            circuit_breaker_config: Circuit breaker settings
        """
        self.base_url = base_url.rstrip("/")
        self.auth_type = auth_type
        self.auth_config = auth_config or {}
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

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
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
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

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> AlertmanagerResult:
        """Make an HTTP request to Alertmanager."""
        if not await self.circuit_breaker.can_execute():
            return AlertmanagerResult(
                status="error",
                error="Circuit breaker is open - Alertmanager unavailable",
            )

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_client()

                if method == "GET":
                    response = await client.get(endpoint, params=params)
                elif method == "POST":
                    response = await client.post(endpoint, json=json_data)
                elif method == "DELETE":
                    response = await client.delete(endpoint)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()

                await self.circuit_breaker.record_success()

                # Alertmanager API v2 returns data directly
                result_data = response.json()
                return AlertmanagerResult(
                    status="success",
                    data=result_data,
                )

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    "alertmanager_http_error",
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
                    "alertmanager_request_error",
                    error=str(e),
                    attempt=attempt + 1,
                )
                await self.circuit_breaker.record_failure()
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                break

        return AlertmanagerResult(
            status="error",
            error=str(last_error) if last_error else "Unknown error",
        )

    async def get_alerts(
        self,
        active: bool = True,
        silenced: bool = True,
        inhibited: bool = True,
        unprocessed: bool = True,
        filter_labels: Optional[Dict[str, str]] = None,
        receiver: Optional[str] = None,
    ) -> AlertmanagerResult:
        """
        Get alerts from Alertmanager.

        Args:
            active: Include active alerts
            silenced: Include silenced alerts
            inhibited: Include inhibited alerts
            unprocessed: Include unprocessed alerts
            filter_labels: Label matchers
            receiver: Filter by receiver

        Returns:
            AlertmanagerResult with alerts
        """
        params: Dict[str, Any] = {
            "active": str(active).lower(),
            "silenced": str(silenced).lower(),
            "inhibited": str(inhibited).lower(),
            "unprocessed": str(unprocessed).lower(),
        }

        if filter_labels:
            # Build filter parameter
            filters = [f'{k}="{v}"' for k, v in filter_labels.items()]
            params["filter"] = filters

        if receiver:
            params["receiver"] = receiver

        return await self._request("GET", "/api/v2/alerts", params=params)

    async def get_alert_groups(
        self,
        active: bool = True,
        silenced: bool = True,
        inhibited: bool = True,
        filter_labels: Optional[Dict[str, str]] = None,
        receiver: Optional[str] = None,
    ) -> AlertmanagerResult:
        """Get alert groups."""
        params: Dict[str, Any] = {
            "active": str(active).lower(),
            "silenced": str(silenced).lower(),
            "inhibited": str(inhibited).lower(),
        }

        if filter_labels:
            filters = [f'{k}="{v}"' for k, v in filter_labels.items()]
            params["filter"] = filters

        if receiver:
            params["receiver"] = receiver

        return await self._request("GET", "/api/v2/alerts/groups", params=params)

    async def get_silences(self, filter_labels: Optional[Dict[str, str]] = None) -> AlertmanagerResult:
        """
        Get all silences.

        Args:
            filter_labels: Label matchers

        Returns:
            AlertmanagerResult with silences
        """
        params = {}
        if filter_labels:
            filters = [f'{k}="{v}"' for k, v in filter_labels.items()]
            params["filter"] = filters

        return await self._request("GET", "/api/v2/silences", params=params)

    async def create_silence(
        self,
        matchers: List[Dict[str, Any]],
        starts_at: datetime,
        ends_at: datetime,
        created_by: str,
        comment: str,
    ) -> AlertmanagerResult:
        """
        Create a new silence.

        Args:
            matchers: Label matchers for the silence
            starts_at: Silence start time
            ends_at: Silence end time
            created_by: Creator identifier
            comment: Silence comment

        Returns:
            AlertmanagerResult with silence ID
        """
        json_data = {
            "matchers": matchers,
            "startsAt": starts_at.isoformat() + "Z",
            "endsAt": ends_at.isoformat() + "Z",
            "createdBy": created_by,
            "comment": comment,
        }

        return await self._request("POST", "/api/v2/silences", json_data=json_data)

    async def delete_silence(self, silence_id: str) -> AlertmanagerResult:
        """
        Delete a silence.

        Args:
            silence_id: Silence ID to delete

        Returns:
            AlertmanagerResult
        """
        return await self._request("DELETE", f"/api/v2/silence/{silence_id}")

    async def get_status(self) -> AlertmanagerResult:
        """Get Alertmanager status."""
        return await self._request("GET", "/api/v2/status")

    async def get_receivers(self) -> AlertmanagerResult:
        """Get all receivers."""
        return await self._request("GET", "/api/v2/receivers")

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check Alertmanager server health.

        Returns:
            Tuple of (is_healthy, message)
        """
        try:
            result = await self.get_status()
            if result.status == "success":
                return True, "Alertmanager is healthy"
            return False, result.error or "Unknown error"
        except Exception as e:
            return False, str(e)

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    async def get_firing_alerts(
        self,
        severity: Optional[str] = None,
        filter_labels: Optional[Dict[str, str]] = None,
    ) -> List[Alert]:
        """
        Get currently firing alerts.

        Args:
            severity: Filter by severity (critical, warning, info)
            filter_labels: Additional label filters

        Returns:
            List of firing alerts
        """
        labels = filter_labels or {}
        if severity:
            labels["severity"] = severity

        result = await self.get_alerts(
            active=True,
            silenced=False,
            inhibited=False,
            unprocessed=True,
            filter_labels=labels if labels else None,
        )

        if result.status == "success" and result.data:
            return [Alert(**alert) for alert in result.data]
        return []

    async def get_alert_count_by_severity(self) -> Dict[str, int]:
        """
        Get alert counts grouped by severity.

        Returns:
            Dict mapping severity to count
        """
        result = await self.get_alerts(active=True, silenced=False, inhibited=False)

        counts: Dict[str, int] = {"critical": 0, "warning": 0, "info": 0}

        if result.status == "success" and result.data:
            for alert in result.data:
                severity = alert.get("labels", {}).get("severity", "info")
                if severity in counts:
                    counts[severity] += 1
                else:
                    counts["info"] += 1

        return counts

    async def silence_alert(
        self,
        fingerprint: str,
        duration_hours: int,
        created_by: str,
        comment: str,
    ) -> AlertmanagerResult:
        """
        Silence a specific alert by fingerprint.

        Args:
            fingerprint: Alert fingerprint
            duration_hours: Silence duration in hours
            created_by: Creator identifier
            comment: Silence comment

        Returns:
            AlertmanagerResult
        """
        # Get the alert to extract its labels
        result = await self.get_alerts()
        if result.status != "success" or not result.data:
            return AlertmanagerResult(status="error", error="Failed to get alerts")

        # Find the alert
        target_alert = None
        for alert in result.data:
            if alert.get("fingerprint") == fingerprint:
                target_alert = alert
                break

        if not target_alert:
            return AlertmanagerResult(status="error", error=f"Alert {fingerprint} not found")

        # Build matchers from alert labels
        labels = target_alert.get("labels", {})
        matchers = [
            {"name": k, "value": v, "isRegex": False}
            for k, v in labels.items()
        ]

        now = datetime.utcnow()
        ends_at = now + datetime.timedelta(hours=duration_hours)

        return await self.create_silence(
            matchers=matchers,
            starts_at=now,
            ends_at=ends_at,
            created_by=created_by,
            comment=comment,
        )
