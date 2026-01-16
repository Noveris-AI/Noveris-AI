"""
Monitoring API Schemas.

Pydantic models for request/response validation in the monitoring module.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Enums
# =============================================================================

class TimeRange(str, Enum):
    """Predefined time ranges for queries."""

    MINUTES_15 = "15m"
    HOUR_1 = "1h"
    HOURS_6 = "6h"
    HOURS_24 = "24h"
    DAYS_7 = "7d"
    DAYS_30 = "30d"
    CUSTOM = "custom"


class HealthStatus(str, Enum):
    """Health status indicators."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class DisplayMode(str, Enum):
    """Display mode for dashboards."""

    SIMPLE = "simple"
    ADVANCED = "advanced"


# =============================================================================
# Common Models
# =============================================================================

class TimeRangeParams(BaseModel):
    """Time range parameters for queries."""

    range: TimeRange = TimeRange.HOUR_1
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    step: Optional[str] = None  # e.g., "1m", "5m", "1h"

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class MetricPoint(BaseModel):
    """Single metric data point."""

    timestamp: float
    value: float


class MetricSeries(BaseModel):
    """Time series data for a metric."""

    name: str
    labels: Dict[str, str] = Field(default_factory=dict)
    points: List[List[Union[float, int]]] = Field(default_factory=list)  # [[timestamp, value], ...]


class MetricResponse(BaseModel):
    """Response containing metric time series data."""

    series: List[MetricSeries] = Field(default_factory=list)
    unit: Optional[str] = None
    suggested_thresholds: Optional[Dict[str, float]] = None


class HelpTooltip(BaseModel):
    """Help information for metrics."""

    description: str
    causes: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)


# =============================================================================
# Overview Card Models
# =============================================================================

class SparklineData(BaseModel):
    """Mini chart data for overview cards."""

    points: List[List[float]] = Field(default_factory=list)  # [[timestamp, value], ...]
    trend: Optional[str] = None  # up, down, stable


class KeyMetric(BaseModel):
    """Key metric displayed on a card."""

    name: str
    value: Union[float, int, str]
    unit: Optional[str] = None
    status: HealthStatus = HealthStatus.UNKNOWN
    change_percent: Optional[float] = None


class OverviewCard(BaseModel):
    """Overview dashboard card."""

    key: str
    title_i18n_key: str
    description_i18n_key: Optional[str] = None
    status: HealthStatus = HealthStatus.UNKNOWN
    key_metrics: List[KeyMetric] = Field(default_factory=list)
    sparkline: Optional[SparklineData] = None
    help_tooltip: Optional[HelpTooltip] = None
    route: str  # Navigation route when clicked


class OverviewResponse(BaseModel):
    """Overview dashboard response."""

    cards: List[OverviewCard] = Field(default_factory=list)
    last_updated: datetime
    data_sources_status: Dict[str, HealthStatus] = Field(default_factory=dict)


# =============================================================================
# Node Models
# =============================================================================

class NodeSummary(BaseModel):
    """Node summary for listing."""

    id: UUID
    hostname: str
    ip_address: Optional[str] = None
    status: HealthStatus = HealthStatus.UNKNOWN
    last_seen: Optional[datetime] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    accelerator_count: int = 0
    role: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)


class NodeMetrics(BaseModel):
    """Detailed node metrics."""

    node_id: UUID
    cpu: MetricResponse
    memory: MetricResponse
    disk: MetricResponse
    network: MetricResponse
    load: MetricResponse
    filesystem: MetricResponse


class NodeEvent(BaseModel):
    """Node-related event."""

    id: UUID
    type: str
    level: str
    title: str
    timestamp: datetime
    payload: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Accelerator Models
# =============================================================================

class AcceleratorSummary(BaseModel):
    """GPU/NPU summary for listing."""

    node_id: UUID
    node_hostname: str
    device_id: str
    vendor: str
    model: str
    status: HealthStatus = HealthStatus.UNKNOWN
    temperature_celsius: Optional[float] = None
    power_watts: Optional[float] = None
    memory_used_bytes: Optional[int] = None
    memory_total_bytes: Optional[int] = None
    memory_utilization: Optional[float] = None
    compute_utilization: Optional[float] = None
    fan_speed_rpm: Optional[int] = None


class AcceleratorTopology(BaseModel):
    """Accelerator topology information."""

    node_id: UUID
    devices: List[Dict[str, Any]] = Field(default_factory=list)
    nvlink_topology: Optional[Dict[str, Any]] = None
    pcie_topology: Optional[Dict[str, Any]] = None
    mig_partitions: Optional[List[Dict[str, Any]]] = None
    partial: bool = False
    partial_reason: Optional[str] = None


class AcceleratorMetrics(BaseModel):
    """Detailed accelerator metrics."""

    node_id: UUID
    device_id: str
    temperature: MetricResponse
    power: MetricResponse
    memory: MetricResponse
    compute_utilization: MetricResponse
    ecc_errors: Optional[MetricResponse] = None


# =============================================================================
# Model Service Models
# =============================================================================

class ModelInstanceSummary(BaseModel):
    """Model instance summary."""

    deployment_id: UUID
    node_id: UUID
    node_hostname: str
    model_name: str
    engine: str  # vllm, xinference, sglang
    status: HealthStatus = HealthStatus.UNKNOWN
    version: Optional[str] = None
    batch_size: Optional[int] = None
    max_seq_len: Optional[int] = None
    memory_used_bytes: Optional[int] = None
    requests_per_second: Optional[float] = None
    avg_latency_ms: Optional[float] = None


class ModelLatencyMetrics(BaseModel):
    """Model latency metrics."""

    model_name: str
    p50_ms: MetricResponse
    p95_ms: MetricResponse
    p99_ms: MetricResponse
    ttft_ms: Optional[MetricResponse] = None  # Time to first token
    throughput_tokens_per_second: MetricResponse


class ModelEvent(BaseModel):
    """Model-related event."""

    id: UUID
    type: str  # load, unload, error, cold_start
    model_name: str
    node_hostname: str
    timestamp: datetime
    duration_ms: Optional[int] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Gateway Models
# =============================================================================

class GatewayTrafficMetrics(BaseModel):
    """Gateway traffic metrics."""

    requests_per_second: MetricResponse
    success_rate: MetricResponse
    error_rate_5xx: MetricResponse
    timeout_rate: MetricResponse
    circuit_breaker_trips: MetricResponse


class GatewayLatencyMetrics(BaseModel):
    """Gateway latency metrics."""

    p50_ms: MetricResponse
    p95_ms: MetricResponse
    p99_ms: MetricResponse
    upstream_latency_ms: MetricResponse
    cross_node_latency_ms: Optional[MetricResponse] = None


class GatewayCacheMetrics(BaseModel):
    """Gateway cache metrics."""

    hit_rate: MetricResponse
    miss_rate: MetricResponse
    sync_latency_ms: Optional[MetricResponse] = None


class APIKeyUsage(BaseModel):
    """API key usage statistics."""

    api_key_id: UUID
    key_prefix: str
    name: str
    requests_total: int
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    rate_limit_hits: int
    last_used: Optional[datetime] = None


# =============================================================================
# Job/Queue Models
# =============================================================================

class QueueMetrics(BaseModel):
    """Job queue metrics."""

    queue_name: str
    pending_count: int
    running_count: int
    completed_count: int
    failed_count: int
    avg_wait_time_ms: Optional[float] = None
    avg_execution_time_ms: Optional[float] = None


class SchedulerMetrics(BaseModel):
    """Scheduler metrics."""

    scheduling_failures: MetricResponse
    resource_utilization: MetricResponse
    queue_watermark: MetricResponse


class JobTrace(BaseModel):
    """Job trace information (if Tempo enabled)."""

    job_id: UUID
    trace_id: str
    spans: List[Dict[str, Any]] = Field(default_factory=list)
    duration_ms: int
    status: str


# =============================================================================
# Network Models
# =============================================================================

class InterNodeMetrics(BaseModel):
    """Inter-node network metrics."""

    source_node: str
    target_node: str
    tcp_retransmits: MetricResponse
    bandwidth_bytes: MetricResponse
    latency_ms: MetricResponse


class BlackboxProbeResult(BaseModel):
    """External dependency probe result."""

    target: str
    target_type: str  # http, dns, tcp
    status: HealthStatus
    latency_ms: Optional[float] = None
    ssl_days_remaining: Optional[int] = None
    last_check: datetime


class StorageMetrics(BaseModel):
    """Storage network metrics."""

    storage_type: str  # nfs, ceph, oss
    read_bytes_per_second: MetricResponse
    write_bytes_per_second: MetricResponse
    latency_ms: MetricResponse
    availability: HealthStatus


# =============================================================================
# Cost Models
# =============================================================================

class CostSummary(BaseModel):
    """Cost summary."""

    scope: str
    scope_id: Optional[str] = None
    scope_name: Optional[str] = None
    compute_cost: Decimal
    energy_cost: Decimal
    token_cost: Decimal
    total_cost: Decimal
    currency: str
    period_start: datetime
    period_end: datetime


class CostBreakdown(BaseModel):
    """Detailed cost breakdown."""

    by_node: List[CostSummary] = Field(default_factory=list)
    by_model: List[CostSummary] = Field(default_factory=list)
    by_api_key: List[CostSummary] = Field(default_factory=list)
    total: CostSummary


class BudgetStatus(BaseModel):
    """Budget status."""

    id: UUID
    name: str
    scope: str
    limit_amount: Decimal
    current_spending: Decimal
    usage_percent: float
    status: str  # normal, warning, exceeded
    currency: str
    window: str
    alerts_triggered: List[int] = Field(default_factory=list)


# =============================================================================
# Security Models
# =============================================================================

class SSHLoginEvent(BaseModel):
    """SSH login event."""

    node_hostname: str
    username: str
    source_ip: str
    success: bool
    timestamp: datetime
    failure_reason: Optional[str] = None


class SSHMetrics(BaseModel):
    """SSH security metrics."""

    login_failures_total: MetricResponse
    login_success_total: MetricResponse
    unique_failed_ips: int
    brute_force_attempts: int


class SecurityAnomaly(BaseModel):
    """Security anomaly."""

    id: UUID
    type: str  # unauthorized_access, malicious_ip, etc.
    severity: str
    title: str
    description: str
    source_ip: Optional[str] = None
    target_resource: Optional[str] = None
    timestamp: datetime
    payload: Dict[str, Any] = Field(default_factory=dict)


class FileIntegrityResult(BaseModel):
    """File integrity check result."""

    file_path: str
    expected_hash: str
    actual_hash: Optional[str] = None
    status: str  # verified, mismatch, missing
    last_checked: datetime
    model_name: Optional[str] = None


# =============================================================================
# Alert Models
# =============================================================================

class ActiveAlert(BaseModel):
    """Active alert from Alertmanager."""

    fingerprint: str
    alert_name: str
    severity: str
    status: str  # firing, resolved
    starts_at: datetime
    ends_at: Optional[datetime] = None
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_by: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None


class AlertAckRequest(BaseModel):
    """Alert acknowledgment request."""

    note: Optional[str] = None


class SilenceRequest(BaseModel):
    """Alert silence request."""

    matchers: List[Dict[str, str]]
    starts_at: datetime
    ends_at: datetime
    comment: str
    created_by: str


# =============================================================================
# Settings Models
# =============================================================================

class MonitoringSettingsUpdate(BaseModel):
    """Monitoring settings update request."""

    prometheus_url: Optional[str] = None
    prometheus_enabled: Optional[bool] = None
    loki_url: Optional[str] = None
    loki_enabled: Optional[bool] = None
    tempo_url: Optional[str] = None
    tempo_enabled: Optional[bool] = None
    alertmanager_url: Optional[str] = None
    alertmanager_enabled: Optional[bool] = None
    enabled_domains: Optional[Dict[str, bool]] = None
    default_range: Optional[str] = None
    default_mode: Optional[str] = None


class TargetCreate(BaseModel):
    """Monitoring target creation request."""

    name: str
    description: Optional[str] = None
    type: str
    scrape_url: str
    scrape_interval: str = "30s"
    scrape_timeout: str = "10s"
    metrics_path: str = "/metrics"
    labels: Dict[str, str] = Field(default_factory=dict)
    tls_enabled: bool = False
    basic_auth_enabled: bool = False


class TargetUpdate(BaseModel):
    """Monitoring target update request."""

    name: Optional[str] = None
    description: Optional[str] = None
    scrape_url: Optional[str] = None
    scrape_interval: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    enabled: Optional[bool] = None


class AlertRuleCreate(BaseModel):
    """Alert rule creation request."""

    name: str
    description: Optional[str] = None
    group: str = "default"
    expr: str
    for_duration: str = "5m"
    severity: str = "warning"
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    routing: Dict[str, Any] = Field(default_factory=dict)


class AdapterCreate(BaseModel):
    """Accelerator adapter creation request."""

    name: str
    description: Optional[str] = None
    vendor: str
    mode: str
    config: Dict[str, Any]
    mapping: Dict[str, Any]
    label_mapping: Dict[str, str] = Field(default_factory=dict)
    extra_labels: Dict[str, str] = Field(default_factory=dict)


class CostProfileCreate(BaseModel):
    """Cost profile creation request."""

    name: str
    description: Optional[str] = None
    accelerator_prices: Dict[str, Any] = Field(default_factory=dict)
    energy_cost: Dict[str, Any] = Field(default_factory=dict)
    token_prices: Dict[str, Any] = Field(default_factory=dict)
    default_currency: str = "USD"
    is_default: bool = False


class BudgetCreate(BaseModel):
    """Budget creation request."""

    name: str
    description: Optional[str] = None
    scope: str
    scope_target: Optional[str] = None
    limit_amount: Decimal
    limit_currency: str = "USD"
    window: str = "monthly"
    alert_thresholds: List[int] = Field(default_factory=lambda: [50, 80, 100])
    notification_config: Dict[str, Any] = Field(default_factory=dict)
