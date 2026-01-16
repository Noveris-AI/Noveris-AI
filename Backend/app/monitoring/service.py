"""
Monitoring Service.

This module provides the main service layer for the monitoring module:
- Data source client management
- Metric aggregation for dashboard cards
- Multi-tenant filtering
- Health status calculation
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.monitoring.clients.prometheus import PrometheusClient
from app.monitoring.clients.loki import LokiClient
from app.monitoring.clients.alertmanager import AlertmanagerClient
from app.monitoring.models import (
    MonitoringSettings,
    MonitoringTarget,
    MonitoringAdapter,
    MonitoringEvent,
    MonitoringAlertRule,
    MonitoringCostProfile,
    MonitoringBudget,
    EventType,
    EventLevel,
)
from app.monitoring.schemas import (
    HealthStatus,
    TimeRange,
    OverviewCard,
    OverviewResponse,
    KeyMetric,
    SparklineData,
    HelpTooltip,
)
from app.monitoring.normalization.base import BaseAcceleratorAdapter
from app.monitoring.normalization.nvidia import NvidiaDcgmAdapter, NvidiaPrometheusAdapter
from app.monitoring.normalization.ascend import AscendNpuExporterAdapter, AscendPrometheusAdapter

logger = structlog.get_logger(__name__)


class MonitoringService:
    """
    Main service for monitoring operations.

    Manages data source clients and provides aggregated metrics
    for dashboard display.
    """

    def __init__(self, redis_client: Optional[Any] = None):
        """
        Initialize monitoring service.

        Args:
            redis_client: Optional Redis client for caching
        """
        self.redis_client = redis_client
        self._prometheus_clients: Dict[UUID, PrometheusClient] = {}
        self._loki_clients: Dict[UUID, LokiClient] = {}
        self._alertmanager_clients: Dict[UUID, AlertmanagerClient] = {}
        self._accelerator_adapters: Dict[UUID, List[BaseAcceleratorAdapter]] = {}

    async def get_prometheus_client(
        self,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> Optional[PrometheusClient]:
        """
        Get or create Prometheus client for tenant.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            PrometheusClient or None if not configured/enabled
        """
        if tenant_id in self._prometheus_clients:
            return self._prometheus_clients[tenant_id]

        # Load settings from database
        result = await db.execute(
            select(MonitoringSettings).where(MonitoringSettings.tenant_id == tenant_id)
        )
        settings = result.scalar_one_or_none()

        if not settings or not settings.prometheus_enabled:
            return None

        client = PrometheusClient(
            base_url=settings.prometheus_url,
            auth_type=settings.prometheus_auth_type,
            auth_config=settings.prometheus_auth_config,
            timeout_seconds=settings.query_timeout_seconds,
            cache_ttl_seconds=settings.cache_ttl_seconds,
            redis_client=self.redis_client,
        )

        self._prometheus_clients[tenant_id] = client
        return client

    async def get_loki_client(
        self,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> Optional[LokiClient]:
        """Get or create Loki client for tenant."""
        if tenant_id in self._loki_clients:
            return self._loki_clients[tenant_id]

        result = await db.execute(
            select(MonitoringSettings).where(MonitoringSettings.tenant_id == tenant_id)
        )
        settings = result.scalar_one_or_none()

        if not settings or not settings.loki_enabled:
            return None

        client = LokiClient(
            base_url=settings.loki_url,
            auth_config=settings.loki_auth_config,
            timeout_seconds=settings.query_timeout_seconds,
        )

        self._loki_clients[tenant_id] = client
        return client

    async def get_alertmanager_client(
        self,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> Optional[AlertmanagerClient]:
        """Get or create Alertmanager client for tenant."""
        if tenant_id in self._alertmanager_clients:
            return self._alertmanager_clients[tenant_id]

        result = await db.execute(
            select(MonitoringSettings).where(MonitoringSettings.tenant_id == tenant_id)
        )
        settings = result.scalar_one_or_none()

        if not settings or not settings.alertmanager_enabled:
            return None

        client = AlertmanagerClient(
            base_url=settings.alertmanager_url,
            auth_config=settings.alertmanager_auth_config,
            timeout_seconds=settings.query_timeout_seconds,
        )

        self._alertmanager_clients[tenant_id] = client
        return client

    async def check_data_sources_health(
        self,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> Dict[str, HealthStatus]:
        """
        Check health of all configured data sources.

        Args:
            db: Database session
            tenant_id: Tenant ID

        Returns:
            Dict mapping source name to health status
        """
        health = {}

        # Check Prometheus
        prom = await self.get_prometheus_client(db, tenant_id)
        if prom:
            is_healthy, _ = await prom.health_check()
            health["prometheus"] = HealthStatus.OK if is_healthy else HealthStatus.CRITICAL
        else:
            health["prometheus"] = HealthStatus.UNKNOWN

        # Check Loki
        loki = await self.get_loki_client(db, tenant_id)
        if loki:
            is_healthy, _ = await loki.health_check()
            health["loki"] = HealthStatus.OK if is_healthy else HealthStatus.CRITICAL
        else:
            health["loki"] = HealthStatus.UNKNOWN

        # Check Alertmanager
        am = await self.get_alertmanager_client(db, tenant_id)
        if am:
            is_healthy, _ = await am.health_check()
            health["alertmanager"] = HealthStatus.OK if is_healthy else HealthStatus.CRITICAL
        else:
            health["alertmanager"] = HealthStatus.UNKNOWN

        return health

    def _parse_time_range(self, range_str: str) -> Tuple[datetime, datetime, str]:
        """
        Parse time range string to start/end times.

        Args:
            range_str: Time range (15m, 1h, 6h, 24h, 7d, 30d)

        Returns:
            Tuple of (start, end, step)
        """
        end = datetime.utcnow()

        ranges = {
            "15m": (timedelta(minutes=15), "1m"),
            "1h": (timedelta(hours=1), "1m"),
            "6h": (timedelta(hours=6), "5m"),
            "24h": (timedelta(hours=24), "15m"),
            "7d": (timedelta(days=7), "1h"),
            "30d": (timedelta(days=30), "4h"),
        }

        delta, step = ranges.get(range_str, (timedelta(hours=1), "1m"))
        start = end - delta

        return start, end, step

    def _calculate_status(
        self,
        value: Optional[float],
        warning_threshold: Optional[float],
        critical_threshold: Optional[float],
        inverse: bool = False,
    ) -> HealthStatus:
        """
        Calculate health status based on thresholds.

        Args:
            value: Metric value
            warning_threshold: Warning threshold
            critical_threshold: Critical threshold
            inverse: If True, lower values are worse

        Returns:
            HealthStatus
        """
        if value is None:
            return HealthStatus.UNKNOWN

        if inverse:
            # Lower is worse (e.g., availability)
            if critical_threshold and value <= critical_threshold:
                return HealthStatus.CRITICAL
            if warning_threshold and value <= warning_threshold:
                return HealthStatus.WARNING
        else:
            # Higher is worse (e.g., CPU usage)
            if critical_threshold and value >= critical_threshold:
                return HealthStatus.CRITICAL
            if warning_threshold and value >= warning_threshold:
                return HealthStatus.WARNING

        return HealthStatus.OK

    async def get_overview_cards(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        time_range: str = "1h",
    ) -> OverviewResponse:
        """
        Get overview dashboard cards with aggregated metrics.

        Args:
            db: Database session
            tenant_id: Tenant ID
            time_range: Time range for queries

        Returns:
            OverviewResponse with card data
        """
        start, end, step = self._parse_time_range(time_range)
        prom = await self.get_prometheus_client(db, tenant_id)

        # Get enabled domains
        result = await db.execute(
            select(MonitoringSettings).where(MonitoringSettings.tenant_id == tenant_id)
        )
        settings = result.scalar_one_or_none()

        enabled_domains = settings.enabled_domains if settings else {}
        cards = []

        # Build cards based on enabled domains
        if enabled_domains.get("nodes", True):
            card = await self._build_nodes_card(prom, start, end, step)
            cards.append(card)

        if enabled_domains.get("accelerators", True):
            card = await self._build_accelerators_card(prom, start, end, step)
            cards.append(card)

        if enabled_domains.get("models", True):
            card = await self._build_models_card(prom, start, end, step)
            cards.append(card)

        if enabled_domains.get("gateway", True):
            card = await self._build_gateway_card(prom, start, end, step)
            cards.append(card)

        if enabled_domains.get("jobs", True):
            card = await self._build_jobs_card(prom, start, end, step)
            cards.append(card)

        if enabled_domains.get("network", True):
            card = await self._build_network_card(prom, start, end, step)
            cards.append(card)

        if enabled_domains.get("cost", True):
            card = await self._build_cost_card(db, tenant_id, start, end)
            cards.append(card)

        if enabled_domains.get("security", True):
            loki = await self.get_loki_client(db, tenant_id)
            card = await self._build_security_card(loki, start, end)
            cards.append(card)

        # Get data sources health
        data_sources_status = await self.check_data_sources_health(db, tenant_id)

        return OverviewResponse(
            cards=cards,
            last_updated=datetime.utcnow(),
            data_sources_status=data_sources_status,
        )

    async def _build_nodes_card(
        self,
        prom: Optional[PrometheusClient],
        start: datetime,
        end: datetime,
        step: str,
    ) -> OverviewCard:
        """Build nodes overview card."""
        key_metrics = []
        status = HealthStatus.UNKNOWN
        sparkline = None

        if prom:
            try:
                # Get node count
                result = await prom.query('count(up{job="node"})')
                total_nodes = 0
                if result.status == "success" and result.data.get("result"):
                    total_nodes = int(float(result.data["result"][0]["value"][1]))

                # Get nodes up
                result = await prom.query('count(up{job="node"} == 1)')
                nodes_up = 0
                if result.status == "success" and result.data.get("result"):
                    nodes_up = int(float(result.data["result"][0]["value"][1]))

                key_metrics.append(KeyMetric(
                    name="nodes_up",
                    value=nodes_up,
                    unit="nodes",
                    status=HealthStatus.OK if nodes_up == total_nodes else HealthStatus.WARNING,
                ))

                # Get average CPU usage
                result = await prom.query('avg(100 - (avg by(instance)(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))')
                avg_cpu = None
                if result.status == "success" and result.data.get("result"):
                    avg_cpu = float(result.data["result"][0]["value"][1])
                    cpu_status = self._calculate_status(avg_cpu, 70, 90)
                    key_metrics.append(KeyMetric(
                        name="avg_cpu",
                        value=round(avg_cpu, 1),
                        unit="%",
                        status=cpu_status,
                    ))

                # Get average memory usage
                result = await prom.query('avg((1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100)')
                avg_mem = None
                if result.status == "success" and result.data.get("result"):
                    avg_mem = float(result.data["result"][0]["value"][1])
                    mem_status = self._calculate_status(avg_mem, 80, 95)
                    key_metrics.append(KeyMetric(
                        name="avg_memory",
                        value=round(avg_mem, 1),
                        unit="%",
                        status=mem_status,
                    ))

                # Determine overall status
                if nodes_up == 0:
                    status = HealthStatus.CRITICAL
                elif nodes_up < total_nodes:
                    status = HealthStatus.WARNING
                else:
                    status = HealthStatus.OK

                # Get sparkline data (nodes up over time)
                result = await prom.query_range(
                    'count(up{job="node"} == 1)',
                    start, end, step
                )
                if result.status == "success" and result.data.get("result"):
                    points = result.data["result"][0].get("values", [])
                    sparkline = SparklineData(
                        points=[[float(p[0]), float(p[1])] for p in points[-20:]],
                    )

            except Exception as e:
                logger.error("nodes_card_error", error=str(e))
                status = HealthStatus.UNKNOWN

        return OverviewCard(
            key="nodes",
            title_i18n_key="monitoring.cards.nodes.title",
            description_i18n_key="monitoring.cards.nodes.description",
            status=status,
            key_metrics=key_metrics,
            sparkline=sparkline,
            help_tooltip=HelpTooltip(
                description="Overview of cluster node health and resource utilization",
                causes=["Hardware failure", "Network issues", "Resource exhaustion"],
                actions=["Check node connectivity", "Review system logs", "Scale cluster"],
            ),
            route="/monitoring/nodes",
        )

    async def _build_accelerators_card(
        self,
        prom: Optional[PrometheusClient],
        start: datetime,
        end: datetime,
        step: str,
    ) -> OverviewCard:
        """Build GPU/NPU accelerators overview card."""
        key_metrics = []
        status = HealthStatus.UNKNOWN
        sparkline = None

        if prom:
            try:
                # Try NVIDIA DCGM metrics first
                result = await prom.query('count(DCGM_FI_DEV_GPU_TEMP)')
                gpu_count = 0
                if result.status == "success" and result.data.get("result"):
                    gpu_count = int(float(result.data["result"][0]["value"][1]))

                # Try Ascend NPU metrics if no NVIDIA
                if gpu_count == 0:
                    result = await prom.query('count(npu_chip_info_temperature)')
                    if result.status == "success" and result.data.get("result"):
                        gpu_count = int(float(result.data["result"][0]["value"][1]))

                key_metrics.append(KeyMetric(
                    name="accelerator_count",
                    value=gpu_count,
                    unit="devices",
                    status=HealthStatus.OK if gpu_count > 0 else HealthStatus.WARNING,
                ))

                if gpu_count > 0:
                    # Get max temperature
                    result = await prom.query('max(DCGM_FI_DEV_GPU_TEMP) or max(npu_chip_info_temperature)')
                    if result.status == "success" and result.data.get("result"):
                        max_temp = float(result.data["result"][0]["value"][1])
                        temp_status = self._calculate_status(max_temp, 75, 85)
                        key_metrics.append(KeyMetric(
                            name="max_temp",
                            value=round(max_temp, 1),
                            unit="°C",
                            status=temp_status,
                        ))

                    # Get average utilization
                    result = await prom.query('avg(DCGM_FI_DEV_GPU_UTIL) or avg(npu_chip_info_utilization)')
                    if result.status == "success" and result.data.get("result"):
                        avg_util = float(result.data["result"][0]["value"][1])
                        key_metrics.append(KeyMetric(
                            name="avg_utilization",
                            value=round(avg_util, 1),
                            unit="%",
                            status=HealthStatus.OK,
                        ))

                    status = HealthStatus.OK
                else:
                    status = HealthStatus.UNKNOWN

            except Exception as e:
                logger.error("accelerators_card_error", error=str(e))

        return OverviewCard(
            key="accelerators",
            title_i18n_key="monitoring.cards.accelerators.title",
            description_i18n_key="monitoring.cards.accelerators.description",
            status=status,
            key_metrics=key_metrics,
            sparkline=sparkline,
            help_tooltip=HelpTooltip(
                description="GPU/NPU device health and utilization metrics",
                causes=["Overheating", "Driver issues", "Memory exhaustion"],
                actions=["Check cooling", "Update drivers", "Reduce batch size"],
            ),
            route="/monitoring/accelerators",
        )

    async def _build_models_card(
        self,
        prom: Optional[PrometheusClient],
        start: datetime,
        end: datetime,
        step: str,
    ) -> OverviewCard:
        """Build model services overview card."""
        key_metrics = []
        status = HealthStatus.UNKNOWN
        sparkline = None

        if prom:
            try:
                # vLLM metrics
                result = await prom.query('count(vllm:num_requests_running) or count(vllm_num_requests_running)')
                model_count = 0
                if result.status == "success" and result.data.get("result"):
                    model_count = int(float(result.data["result"][0]["value"][1]))

                key_metrics.append(KeyMetric(
                    name="model_instances",
                    value=model_count,
                    unit="instances",
                    status=HealthStatus.OK if model_count > 0 else HealthStatus.WARNING,
                ))

                if model_count > 0:
                    # Get P99 latency
                    result = await prom.query(
                        'histogram_quantile(0.99, sum(rate(vllm:e2e_request_latency_seconds_bucket[5m])) by (le))'
                    )
                    if result.status == "success" and result.data.get("result"):
                        p99_latency = float(result.data["result"][0]["value"][1]) * 1000  # Convert to ms
                        latency_status = self._calculate_status(p99_latency, 5000, 10000)
                        key_metrics.append(KeyMetric(
                            name="p99_latency",
                            value=round(p99_latency, 0),
                            unit="ms",
                            status=latency_status,
                        ))

                    status = HealthStatus.OK
                else:
                    status = HealthStatus.UNKNOWN

            except Exception as e:
                logger.error("models_card_error", error=str(e))

        return OverviewCard(
            key="models",
            title_i18n_key="monitoring.cards.models.title",
            description_i18n_key="monitoring.cards.models.description",
            status=status,
            key_metrics=key_metrics,
            sparkline=sparkline,
            help_tooltip=HelpTooltip(
                description="Model service performance and availability",
                causes=["Cold start", "Resource contention", "Model errors"],
                actions=["Check model logs", "Scale replicas", "Optimize batch size"],
            ),
            route="/monitoring/models",
        )

    async def _build_gateway_card(
        self,
        prom: Optional[PrometheusClient],
        start: datetime,
        end: datetime,
        step: str,
    ) -> OverviewCard:
        """Build gateway overview card."""
        key_metrics = []
        status = HealthStatus.UNKNOWN
        sparkline = None

        if prom:
            try:
                # Request rate
                result = await prom.query('sum(rate(http_requests_total{job="gateway"}[5m]))')
                if result.status == "success" and result.data.get("result"):
                    qps = float(result.data["result"][0]["value"][1])
                    key_metrics.append(KeyMetric(
                        name="requests_per_second",
                        value=round(qps, 2),
                        unit="req/s",
                        status=HealthStatus.OK,
                    ))

                # Error rate
                result = await prom.query(
                    'sum(rate(http_requests_total{job="gateway",status=~"5.."}[5m])) / sum(rate(http_requests_total{job="gateway"}[5m])) * 100'
                )
                if result.status == "success" and result.data.get("result"):
                    error_rate = float(result.data["result"][0]["value"][1])
                    error_status = self._calculate_status(error_rate, 1, 5)
                    key_metrics.append(KeyMetric(
                        name="error_rate",
                        value=round(error_rate, 2),
                        unit="%",
                        status=error_status,
                    ))

                    status = error_status if key_metrics else HealthStatus.OK
                else:
                    status = HealthStatus.OK

            except Exception as e:
                logger.error("gateway_card_error", error=str(e))

        return OverviewCard(
            key="gateway",
            title_i18n_key="monitoring.cards.gateway.title",
            description_i18n_key="monitoring.cards.gateway.description",
            status=status,
            key_metrics=key_metrics,
            sparkline=sparkline,
            help_tooltip=HelpTooltip(
                description="API gateway traffic and error rates",
                causes=["Upstream failures", "Rate limiting", "Timeout"],
                actions=["Check upstream health", "Review rate limits", "Adjust timeouts"],
            ),
            route="/monitoring/gateway",
        )

    async def _build_jobs_card(
        self,
        prom: Optional[PrometheusClient],
        start: datetime,
        end: datetime,
        step: str,
    ) -> OverviewCard:
        """Build jobs/queue overview card."""
        key_metrics = []
        status = HealthStatus.UNKNOWN

        # Placeholder - would query Celery/task queue metrics
        key_metrics.append(KeyMetric(
            name="pending_jobs",
            value=0,
            unit="jobs",
            status=HealthStatus.OK,
        ))
        status = HealthStatus.OK

        return OverviewCard(
            key="jobs",
            title_i18n_key="monitoring.cards.jobs.title",
            description_i18n_key="monitoring.cards.jobs.description",
            status=status,
            key_metrics=key_metrics,
            sparkline=None,
            help_tooltip=HelpTooltip(
                description="Task queue and job scheduler metrics",
                causes=["Queue backlog", "Worker failures", "Resource limits"],
                actions=["Scale workers", "Review failed jobs", "Check priorities"],
            ),
            route="/monitoring/jobs",
        )

    async def _build_network_card(
        self,
        prom: Optional[PrometheusClient],
        start: datetime,
        end: datetime,
        step: str,
    ) -> OverviewCard:
        """Build network overview card."""
        key_metrics = []
        status = HealthStatus.UNKNOWN

        if prom:
            try:
                # Blackbox probe success
                result = await prom.query('avg(probe_success)')
                if result.status == "success" and result.data.get("result"):
                    probe_success = float(result.data["result"][0]["value"][1]) * 100
                    probe_status = self._calculate_status(probe_success, 99, 95, inverse=True)
                    key_metrics.append(KeyMetric(
                        name="probe_success",
                        value=round(probe_success, 1),
                        unit="%",
                        status=probe_status,
                    ))
                    status = probe_status
                else:
                    status = HealthStatus.OK

            except Exception as e:
                logger.error("network_card_error", error=str(e))

        return OverviewCard(
            key="network",
            title_i18n_key="monitoring.cards.network.title",
            description_i18n_key="monitoring.cards.network.description",
            status=status,
            key_metrics=key_metrics,
            sparkline=None,
            help_tooltip=HelpTooltip(
                description="Network connectivity and external dependency health",
                causes=["Network partition", "DNS issues", "External service down"],
                actions=["Check connectivity", "Verify DNS", "Contact provider"],
            ),
            route="/monitoring/network",
        )

    async def _build_cost_card(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
    ) -> OverviewCard:
        """Build cost overview card."""
        key_metrics = []
        status = HealthStatus.OK

        # Query budget status
        result = await db.execute(
            select(MonitoringBudget).where(
                MonitoringBudget.tenant_id == tenant_id,
                MonitoringBudget.enabled == True,
            )
        )
        budgets = result.scalars().all()

        total_spending = sum(float(b.current_spending or 0) for b in budgets)
        total_limit = sum(float(b.limit_amount or 0) for b in budgets)

        key_metrics.append(KeyMetric(
            name="current_spending",
            value=round(total_spending, 2),
            unit="USD",
            status=HealthStatus.OK,
        ))

        if total_limit > 0:
            usage_percent = (total_spending / total_limit) * 100
            budget_status = self._calculate_status(usage_percent, 80, 100)
            key_metrics.append(KeyMetric(
                name="budget_usage",
                value=round(usage_percent, 1),
                unit="%",
                status=budget_status,
            ))
            status = budget_status

        return OverviewCard(
            key="cost",
            title_i18n_key="monitoring.cards.cost.title",
            description_i18n_key="monitoring.cards.cost.description",
            status=status,
            key_metrics=key_metrics,
            sparkline=None,
            help_tooltip=HelpTooltip(
                description="Resource usage cost and budget tracking",
                causes=["Increased usage", "Price changes", "Resource waste"],
                actions=["Review usage", "Optimize resources", "Adjust budget"],
            ),
            route="/monitoring/cost",
        )

    async def _build_security_card(
        self,
        loki: Optional[LokiClient],
        start: datetime,
        end: datetime,
    ) -> OverviewCard:
        """Build security overview card."""
        key_metrics = []
        status = HealthStatus.OK

        if loki:
            try:
                # Get SSH login failures
                result = await loki.search_logs(
                    labels={"job": "syslog"},
                    regex_pattern="Failed password|Invalid user",
                    start=start,
                    end=end,
                    limit=1000,
                )

                failure_count = len(result.data.get("result", []))
                failure_status = self._calculate_status(failure_count, 10, 50)

                key_metrics.append(KeyMetric(
                    name="ssh_failures",
                    value=failure_count,
                    unit="events",
                    status=failure_status,
                ))

                status = failure_status

            except Exception as e:
                logger.error("security_card_error", error=str(e))

        return OverviewCard(
            key="security",
            title_i18n_key="monitoring.cards.security.title",
            description_i18n_key="monitoring.cards.security.description",
            status=status,
            key_metrics=key_metrics,
            sparkline=None,
            help_tooltip=HelpTooltip(
                description="Security events and threat monitoring",
                causes=["Brute force attacks", "Unauthorized access", "Configuration issues"],
                actions=["Review logs", "Block suspicious IPs", "Strengthen auth"],
            ),
            route="/monitoring/security",
        )

    async def record_event(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        event_type: EventType,
        level: EventLevel,
        title: str,
        payload: Dict[str, Any] = None,
        node_id: UUID = None,
        model_id: UUID = None,
        source: str = "platform",
        triggered_by: UUID = None,
    ) -> MonitoringEvent:
        """
        Record a monitoring event.

        Args:
            db: Database session
            tenant_id: Tenant ID
            event_type: Event type
            level: Event level
            title: Event title
            payload: Event payload
            node_id: Related node ID
            model_id: Related model ID
            source: Event source
            triggered_by: User who triggered the event

        Returns:
            Created MonitoringEvent
        """
        event = MonitoringEvent(
            tenant_id=tenant_id,
            type=event_type,
            level=level,
            title=title,
            payload=payload or {},
            node_id=node_id,
            model_id=model_id,
            source=source,
            triggered_by=triggered_by,
        )

        db.add(event)
        await db.flush()

        logger.info(
            "monitoring_event_recorded",
            event_id=str(event.id),
            event_type=event_type.value,
            level=level.value,
        )

        return event

    async def close(self) -> None:
        """Close all clients."""
        for client in self._prometheus_clients.values():
            await client.close()
        for client in self._loki_clients.values():
            await client.close()
        for client in self._alertmanager_clients.values():
            await client.close()

        self._prometheus_clients.clear()
        self._loki_clients.clear()
        self._alertmanager_clients.clear()


# Global service instance
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service() -> MonitoringService:
    """Get or create global monitoring service instance."""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service
