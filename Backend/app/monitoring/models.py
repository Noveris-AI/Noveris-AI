"""
Monitoring Database Models.

This module contains all database models for the monitoring system:
- MonitoringSettings: Per-tenant monitoring configuration
- MonitoringTarget: Prometheus scrape targets
- MonitoringAdapter: GPU/NPU metrics normalization adapters
- MonitoringDashboard: Dashboard layout configuration
- MonitoringAlertRule: Alert rule definitions
- MonitoringEvent: Platform events and audit trail
- MonitoringCostProfile: Cost calculation profiles
- MonitoringBudget: Budget and spending alerts
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


# =============================================================================
# Enums
# =============================================================================

class TargetType(str, enum.Enum):
    """Types of monitoring targets."""

    NODE = "node"                    # Node exporter
    GATEWAY = "gateway"              # Gateway metrics
    MODEL = "model"                  # Model service (vLLM, Xinference, etc.)
    ACCELERATOR = "accelerator"      # GPU/NPU exporter
    BLACKBOX = "blackbox"            # Blackbox exporter probes
    CUSTOM = "custom"                # Custom exporter


class AdapterVendor(str, enum.Enum):
    """Accelerator vendors."""

    NVIDIA = "nvidia"
    HUAWEI_ASCEND = "huawei_ascend"
    ALIYUN_NPU = "aliyun_npu"
    AMD = "amd"
    INTEL = "intel"
    CUSTOM = "custom"


class AdapterMode(str, enum.Enum):
    """Data collection modes for adapters."""

    PROMETHEUS = "prometheus"        # Direct Prometheus exporter
    CLOUD_API = "cloud_api"          # Cloud provider API (CloudMonitor, etc.)
    EXEC = "exec"                    # Execute CLI commands


class AlertSeverity(str, enum.Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EventLevel(str, enum.Enum):
    """Event log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventType(str, enum.Enum):
    """Types of monitoring events."""

    # Node events
    NODE_UP = "node_up"
    NODE_DOWN = "node_down"
    NODE_REBOOT = "node_reboot"

    # Model events
    MODEL_LOAD = "model_load"
    MODEL_UNLOAD = "model_unload"
    MODEL_ERROR = "model_error"
    MODEL_COLD_START = "model_cold_start"

    # Gateway events
    ROUTE_CHANGE = "route_change"
    UPSTREAM_CHANGE = "upstream_change"
    CIRCUIT_BREAKER = "circuit_breaker"

    # Alert events
    ALERT_FIRING = "alert_firing"
    ALERT_RESOLVED = "alert_resolved"
    ALERT_ACK = "alert_ack"
    ALERT_SILENCE = "alert_silence"

    # Security events
    SSH_LOGIN_FAILED = "ssh_login_failed"
    SSH_LOGIN_SUCCESS = "ssh_login_success"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    FILE_INTEGRITY_VIOLATION = "file_integrity_violation"

    # Configuration events
    CONFIG_CHANGE = "config_change"
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXCEEDED = "budget_exceeded"

    # System events
    ADAPTER_ERROR = "adapter_error"
    SCRAPE_FAILURE = "scrape_failure"


class BudgetScope(str, enum.Enum):
    """Budget scope types."""

    TENANT = "tenant"
    NODE = "node"
    API_KEY = "api_key"
    MODEL = "model"


class BudgetWindow(str, enum.Enum):
    """Budget time windows."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# =============================================================================
# Models
# =============================================================================

class MonitoringSettings(Base):
    """
    Per-tenant monitoring configuration.

    Stores connection URLs and feature flags for the observability stack.
    """

    __tablename__ = "monitoring_settings"
    __table_args__ = (
        Index("ix_monitoring_settings_tenant_id", "tenant_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, unique=True)

    # Prometheus configuration
    prometheus_url = Column(String(2000), default="http://localhost:9090")
    prometheus_enabled = Column(Boolean, default=True)
    prometheus_auth_type = Column(String(50), default="none")  # none, basic, bearer
    prometheus_auth_config = Column(JSONB, default=dict)  # Encrypted credentials reference

    # Loki configuration
    loki_url = Column(String(2000), default="http://localhost:3100")
    loki_enabled = Column(Boolean, default=True)
    loki_auth_config = Column(JSONB, default=dict)

    # Tempo configuration (optional)
    tempo_url = Column(String(2000), default="http://localhost:3200")
    tempo_enabled = Column(Boolean, default=False)
    tempo_auth_config = Column(JSONB, default=dict)

    # Alertmanager configuration
    alertmanager_url = Column(String(2000), default="http://localhost:9093")
    alertmanager_enabled = Column(Boolean, default=True)
    alertmanager_auth_config = Column(JSONB, default=dict)

    # Feature flags
    enabled_domains = Column(JSONB, default=lambda: {
        "nodes": True,
        "accelerators": True,
        "models": True,
        "gateway": True,
        "jobs": True,
        "network": True,
        "cost": True,
        "security": True,
    })

    # Query settings
    default_range = Column(String(20), default="1h")
    max_range = Column(String(20), default="30d")
    cache_ttl_seconds = Column(Integer, default=30)
    query_timeout_seconds = Column(Integer, default=30)

    # Display settings
    default_mode = Column(String(20), default="simple")  # simple or advanced

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<MonitoringSettings(tenant_id={self.tenant_id})>"


class MonitoringTarget(Base):
    """
    Prometheus scrape target registration.

    Used for dynamic target discovery and management.
    """

    __tablename__ = "monitoring_targets"
    __table_args__ = (
        Index("ix_monitoring_targets_tenant_id", "tenant_id"),
        Index("ix_monitoring_targets_type", "type"),
        Index("ix_monitoring_targets_enabled", "enabled"),
        UniqueConstraint("tenant_id", "scrape_url", name="uq_monitoring_targets_tenant_url"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    type = Column(Enum(TargetType), nullable=False)

    # Scrape configuration
    scrape_url = Column(String(2000), nullable=False)
    scrape_interval = Column(String(20), default="30s")
    scrape_timeout = Column(String(20), default="10s")
    metrics_path = Column(String(500), default="/metrics")

    # TLS configuration
    tls_enabled = Column(Boolean, default=False)
    tls_config = Column(JSONB, default=dict)  # ca_cert, client_cert, client_key refs

    # Basic auth configuration
    basic_auth_enabled = Column(Boolean, default=False)
    basic_auth_config = Column(JSONB, default=dict)  # username, password ref

    # Labels to add to all metrics from this target
    labels = Column(JSONB, default=dict)

    # Related entity (node_id, deployment_id, etc.)
    related_entity_type = Column(String(50))
    related_entity_id = Column(UUID(as_uuid=True))

    enabled = Column(Boolean, default=True, nullable=False)

    # Health tracking
    last_scrape_at = Column(DateTime(timezone=True))
    last_scrape_status = Column(String(50))  # success, timeout, error
    last_scrape_error = Column(Text)
    scrape_sample_count = Column(Integer)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<MonitoringTarget(id={self.id}, name={self.name}, type={self.type})>"


class MonitoringAdapter(Base):
    """
    GPU/NPU metrics normalization adapter configuration.

    Defines how to collect and normalize metrics from different accelerator vendors.
    """

    __tablename__ = "monitoring_adapters"
    __table_args__ = (
        Index("ix_monitoring_adapters_tenant_id", "tenant_id"),
        Index("ix_monitoring_adapters_vendor", "vendor"),
        Index("ix_monitoring_adapters_enabled", "enabled"),
        UniqueConstraint("tenant_id", "name", name="uq_monitoring_adapters_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    vendor = Column(Enum(AdapterVendor), nullable=False)
    mode = Column(Enum(AdapterMode), nullable=False)

    # Configuration based on mode
    # For PROMETHEUS mode:
    # {
    #     "exporter_url": "http://node:9400/metrics",
    #     "metric_prefix": "DCGM_"
    # }
    # For CLOUD_API mode:
    # {
    #     "api_endpoint": "https://metrics.cn-hangzhou.aliyuncs.com",
    #     "region": "cn-hangzhou",
    #     "access_key_ref": "secret_id",
    #     "namespace": "acs_ecs_dashboard"
    # }
    # For EXEC mode:
    # {
    #     "command": "nvidia-smi --query-gpu=...",
    #     "parse_format": "csv",
    #     "interval_seconds": 30
    # }
    config = Column(JSONB, nullable=False, default=dict)

    # Metric mapping: source_metric -> normalized_metric
    # Example for NVIDIA DCGM:
    # {
    #     "DCGM_FI_DEV_GPU_TEMP": {"target": "accelerator_temperature_celsius", "unit": "celsius"},
    #     "DCGM_FI_DEV_POWER_USAGE": {"target": "accelerator_power_watts", "unit": "watts"},
    #     "DCGM_FI_DEV_FB_USED": {"target": "accelerator_memory_used_bytes", "unit": "mib_to_bytes"},
    #     "DCGM_FI_DEV_FB_FREE": {"target": "accelerator_memory_free_bytes", "unit": "mib_to_bytes"},
    #     "DCGM_FI_DEV_GPU_UTIL": {"target": "accelerator_compute_utilization_ratio", "unit": "percent_to_ratio"}
    # }
    mapping = Column(JSONB, nullable=False, default=dict)

    # Label mapping: source_label -> normalized_label
    # Example:
    # {
    #     "gpu": "device_id",
    #     "UUID": "device_uuid",
    #     "modelName": "model"
    # }
    label_mapping = Column(JSONB, default=dict)

    # Additional labels to add
    extra_labels = Column(JSONB, default=dict)

    enabled = Column(Boolean, default=True, nullable=False)

    # Health tracking
    last_collection_at = Column(DateTime(timezone=True))
    last_collection_status = Column(String(50))
    last_collection_error = Column(Text)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<MonitoringAdapter(id={self.id}, name={self.name}, vendor={self.vendor})>"


class MonitoringDashboard(Base):
    """
    Dashboard layout and configuration.

    Stores card layouts, default metrics, and display preferences.
    """

    __tablename__ = "monitoring_dashboards"
    __table_args__ = (
        Index("ix_monitoring_dashboards_tenant_id", "tenant_id"),
        Index("ix_monitoring_dashboards_key", "key"),
        UniqueConstraint("tenant_id", "key", name="uq_monitoring_dashboards_tenant_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Dashboard key (nodes, accelerators, models, gateway, etc.)
    key = Column(String(100), nullable=False)

    # i18n key for title and description
    title_i18n_key = Column(String(255), nullable=False)
    description_i18n_key = Column(String(255))

    # Card layout configuration
    # {
    #     "columns": 3,
    #     "cards": [
    #         {
    #             "id": "node_count",
    #             "position": {"row": 0, "col": 0, "width": 1, "height": 1},
    #             "title_i18n_key": "monitoring.nodes.card.count",
    #             "metrics": ["up{job='node'}"],
    #             "aggregation": "count",
    #             "thresholds": {"warning": null, "critical": 0}
    #         }
    #     ]
    # }
    layout = Column(JSONB, nullable=False, default=dict)

    # Default metrics to show in simple mode
    simple_mode_metrics = Column(JSONB, default=list)

    # Full metrics for advanced mode
    advanced_mode_metrics = Column(JSONB, default=list)

    # Threshold configurations
    # {
    #     "cpu_usage": {"warning": 0.7, "critical": 0.9},
    #     "memory_usage": {"warning": 0.8, "critical": 0.95}
    # }
    thresholds = Column(JSONB, default=dict)

    # Help tooltips (i18n keys)
    # {
    #     "cpu_usage": {
    #         "description_key": "monitoring.help.cpu_usage.desc",
    #         "causes_key": "monitoring.help.cpu_usage.causes",
    #         "actions_key": "monitoring.help.cpu_usage.actions"
    #     }
    # }
    help_tooltips = Column(JSONB, default=dict)

    enabled = Column(Boolean, default=True, nullable=False)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<MonitoringDashboard(id={self.id}, key={self.key})>"


class MonitoringAlertRule(Base):
    """
    Prometheus alert rule definitions.

    Stored in database for dynamic rule management.
    """

    __tablename__ = "monitoring_alert_rules"
    __table_args__ = (
        Index("ix_monitoring_alert_rules_tenant_id", "tenant_id"),
        Index("ix_monitoring_alert_rules_severity", "severity"),
        Index("ix_monitoring_alert_rules_enabled", "enabled"),
        UniqueConstraint("tenant_id", "name", name="uq_monitoring_alert_rules_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    # Alert group (for organizing in Alertmanager)
    group = Column(String(100), default="default")

    # PromQL expression
    expr = Column(Text, nullable=False)

    # Duration before firing
    for_duration = Column(String(20), default="5m")

    severity = Column(Enum(AlertSeverity), nullable=False, default=AlertSeverity.WARNING)

    # Labels to add to the alert
    labels = Column(JSONB, default=dict)

    # Annotations (summary, description templates)
    # {
    #     "summary": "High CPU usage on {{ $labels.instance }}",
    #     "description": "CPU usage is {{ $value }}% on {{ $labels.instance }}"
    # }
    annotations = Column(JSONB, default=dict)

    # Notification routing
    # {
    #     "receiver": "slack-alerts",
    #     "group_by": ["alertname", "cluster"],
    #     "group_wait": "30s",
    #     "group_interval": "5m",
    #     "repeat_interval": "4h"
    # }
    routing = Column(JSONB, default=dict)

    # Template name (for using predefined templates)
    template_name = Column(String(100))
    template_params = Column(JSONB, default=dict)

    enabled = Column(Boolean, default=True, nullable=False)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<MonitoringAlertRule(id={self.id}, name={self.name}, severity={self.severity})>"


class MonitoringEvent(Base):
    """
    Platform monitoring events and audit trail.

    Stores important events for observability and debugging.
    """

    __tablename__ = "monitoring_events"
    __table_args__ = (
        Index("ix_monitoring_events_tenant_id", "tenant_id"),
        Index("ix_monitoring_events_type", "type"),
        Index("ix_monitoring_events_level", "level"),
        Index("ix_monitoring_events_node_id", "node_id"),
        Index("ix_monitoring_events_model_id", "model_id"),
        Index("ix_monitoring_events_created_at", "created_at"),
        Index("ix_monitoring_events_tenant_created", "tenant_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    type = Column(Enum(EventType), nullable=False)
    level = Column(Enum(EventLevel), nullable=False, default=EventLevel.INFO)

    # Related entities
    node_id = Column(UUID(as_uuid=True))
    model_id = Column(UUID(as_uuid=True))
    deployment_id = Column(UUID(as_uuid=True))
    api_key_id = Column(UUID(as_uuid=True))
    alert_fingerprint = Column(String(100))

    # Event title (short summary)
    title = Column(String(500), nullable=False)

    # Event details
    # {
    #     "previous_state": "running",
    #     "new_state": "stopped",
    #     "reason": "OOM killed",
    #     "metrics_at_event": {...}
    # }
    payload = Column(JSONB, default=dict)

    # Source of the event
    source = Column(String(100))  # prometheus, loki, gateway, platform, etc.

    # User who triggered (if applicable)
    triggered_by = Column(UUID(as_uuid=True))

    # For alert events
    alert_acknowledged = Column(Boolean, default=False)
    alert_acknowledged_by = Column(UUID(as_uuid=True))
    alert_acknowledged_at = Column(DateTime(timezone=True))
    alert_acknowledged_note = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<MonitoringEvent(id={self.id}, type={self.type}, level={self.level})>"


class MonitoringCostProfile(Base):
    """
    Cost calculation profiles for billing and budgeting.

    Defines pricing for compute resources, energy, and token usage.
    """

    __tablename__ = "monitoring_cost_profiles"
    __table_args__ = (
        Index("ix_monitoring_cost_profiles_tenant_id", "tenant_id"),
        UniqueConstraint("tenant_id", "name", name="uq_monitoring_cost_profiles_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    # GPU/NPU pricing per hour
    # {
    #     "NVIDIA A100": {"price": 3.5, "currency": "USD"},
    #     "NVIDIA H100": {"price": 8.0, "currency": "USD"},
    #     "Ascend 910B": {"price": 2.5, "currency": "CNY"}
    # }
    accelerator_prices = Column(JSONB, default=dict)

    # Energy cost
    # {
    #     "price_per_kwh": 0.1,
    #     "currency": "USD",
    #     "pue": 1.2  # Power Usage Effectiveness
    # }
    energy_cost = Column(JSONB, default=dict)

    # Token pricing (for API usage)
    # {
    #     "model_patterns": {
    #         "gpt-4*": {"input_per_1k": 0.03, "output_per_1k": 0.06},
    #         "gpt-3.5*": {"input_per_1k": 0.001, "output_per_1k": 0.002},
    #         "default": {"input_per_1k": 0.0001, "output_per_1k": 0.0002}
    #     }
    # }
    token_prices = Column(JSONB, default=dict)

    # Default currency
    default_currency = Column(String(10), default="USD")

    # Mark as default profile for tenant
    is_default = Column(Boolean, default=False)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<MonitoringCostProfile(id={self.id}, name={self.name})>"


class MonitoringBudget(Base):
    """
    Budget configuration and spending alerts.

    Tracks spending against configured limits.
    """

    __tablename__ = "monitoring_budgets"
    __table_args__ = (
        Index("ix_monitoring_budgets_tenant_id", "tenant_id"),
        Index("ix_monitoring_budgets_scope", "scope"),
        Index("ix_monitoring_budgets_enabled", "enabled"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    scope = Column(Enum(BudgetScope), nullable=False)

    # Scope target (tenant_id, node_id, api_key_id, or model name pattern)
    scope_target = Column(String(500))

    # Budget limit
    limit_amount = Column(Numeric(precision=12, scale=2), nullable=False)
    limit_currency = Column(String(10), default="USD")

    window = Column(Enum(BudgetWindow), nullable=False, default=BudgetWindow.MONTHLY)

    # Alert thresholds (percentage of limit)
    # [50, 80, 100, 120] -> alert at 50%, 80%, 100%, 120%
    alert_thresholds = Column(JSONB, default=lambda: [50, 80, 100])

    # Notification configuration
    # {
    #     "email": ["admin@company.com"],
    #     "webhook": "https://hooks.slack.com/...",
    #     "alert_rule_name": "budget_exceeded"
    # }
    notification_config = Column(JSONB, default=dict)

    # Current spending (updated periodically)
    current_spending = Column(Numeric(precision=12, scale=2), default=0)
    current_period_start = Column(DateTime(timezone=True))
    last_updated_at = Column(DateTime(timezone=True))

    # Status
    status = Column(String(20), default="normal")  # normal, warning, exceeded

    enabled = Column(Boolean, default=True, nullable=False)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<MonitoringBudget(id={self.id}, name={self.name}, scope={self.scope})>"
