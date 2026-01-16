"""
Alerting Schemas for Node Management.

Pydantic schemas for alert rules, instances, and notification channels.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


# =============================================================================
# Enums
# =============================================================================

class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class AlertState(str, Enum):
    """Alert instance states."""
    FIRING = "FIRING"
    RESOLVED = "RESOLVED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SILENCED = "SILENCED"


class AlertRuleType(str, Enum):
    """Alert rule types."""
    NODE_STATUS = "node_status"
    METRIC_THRESHOLD = "metric_threshold"
    JOB_FAILURE = "job_failure"
    CONNECTIVITY = "connectivity"
    CUSTOM = "custom"


class NotificationChannelType(str, Enum):
    """Notification channel types."""
    WEBHOOK = "WEBHOOK"
    EMAIL = "EMAIL"
    SLACK = "SLACK"
    PAGERDUTY = "PAGERDUTY"
    TEAMS = "TEAMS"


class ComparisonOperator(str, Enum):
    """Comparison operators for conditions."""
    GT = "gt"  # Greater than
    GTE = "gte"  # Greater than or equal
    LT = "lt"  # Less than
    LTE = "lte"  # Less than or equal
    EQ = "eq"  # Equal
    NEQ = "neq"  # Not equal


# =============================================================================
# Condition Schemas
# =============================================================================

class NodeStatusCondition(BaseModel):
    """Condition for node status alerts."""
    statuses: List[str] = Field(..., description="Node statuses to alert on")
    # e.g., ["UNREACHABLE", "MAINTENANCE"]


class MetricThresholdCondition(BaseModel):
    """Condition for metric threshold alerts."""
    metric_name: str = Field(..., description="Metric name (e.g., cpu_usage, memory_percent)")
    operator: ComparisonOperator = Field(..., description="Comparison operator")
    threshold: float = Field(..., description="Threshold value")
    unit: Optional[str] = Field(None, description="Unit for display (e.g., %, GB)")


class JobFailureCondition(BaseModel):
    """Condition for job failure alerts."""
    job_types: Optional[List[str]] = Field(None, description="Job types to monitor")
    consecutive_failures: int = Field(1, description="Number of consecutive failures")
    include_cancelled: bool = Field(False, description="Include cancelled jobs")


class ConnectivityCondition(BaseModel):
    """Condition for connectivity alerts."""
    timeout_seconds: int = Field(30, description="Connection timeout")
    retry_count: int = Field(3, description="Number of retries before alerting")


class AlertCondition(BaseModel):
    """Generic alert condition wrapper."""
    node_status: Optional[NodeStatusCondition] = None
    metric_threshold: Optional[MetricThresholdCondition] = None
    job_failure: Optional[JobFailureCondition] = None
    connectivity: Optional[ConnectivityCondition] = None


# =============================================================================
# Alert Rule Schemas
# =============================================================================

class AlertRuleBase(BaseModel):
    """Base alert rule schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    enabled: bool = True
    rule_type: AlertRuleType
    severity: AlertSeverity = AlertSeverity.WARNING

    # Targeting
    target_all_nodes: bool = False
    target_node_ids: Optional[List[uuid.UUID]] = None
    target_group_ids: Optional[List[uuid.UUID]] = None
    target_tags: Optional[List[str]] = None

    # Evaluation
    evaluation_interval: int = Field(60, ge=10, le=3600, description="Seconds between evaluations")
    for_duration: int = Field(300, ge=0, le=86400, description="Seconds condition must be true before firing")

    # Notifications
    notification_channel_ids: Optional[List[uuid.UUID]] = None
    notification_template: Optional[str] = None

    # Metadata
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)


class AlertRuleCreate(AlertRuleBase):
    """Schema for creating an alert rule."""
    condition: Dict[str, Any] = Field(..., description="Rule condition configuration")


class AlertRuleUpdate(BaseModel):
    """Schema for updating an alert rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    enabled: Optional[bool] = None
    severity: Optional[AlertSeverity] = None
    condition: Optional[Dict[str, Any]] = None

    target_all_nodes: Optional[bool] = None
    target_node_ids: Optional[List[uuid.UUID]] = None
    target_group_ids: Optional[List[uuid.UUID]] = None
    target_tags: Optional[List[str]] = None

    evaluation_interval: Optional[int] = Field(None, ge=10, le=3600)
    for_duration: Optional[int] = Field(None, ge=0, le=86400)

    notification_channel_ids: Optional[List[uuid.UUID]] = None
    notification_template: Optional[str] = None

    labels: Optional[Dict[str, str]] = None
    annotations: Optional[Dict[str, str]] = None


class AlertRuleResponse(AlertRuleBase):
    """Response schema for alert rule."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    condition: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[uuid.UUID]

    # Computed fields
    active_alerts_count: int = 0

    class Config:
        from_attributes = True


# =============================================================================
# Alert Instance Schemas
# =============================================================================

class AlertInstanceBase(BaseModel):
    """Base alert instance schema."""
    title: str
    message: Optional[str] = None
    severity: AlertSeverity
    state: AlertState


class AlertInstanceResponse(AlertInstanceBase):
    """Response schema for alert instance."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    rule_id: uuid.UUID
    fingerprint: str

    # Context
    node_id: Optional[uuid.UUID]
    node_name: Optional[str]
    group_id: Optional[uuid.UUID]

    # Details
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)

    # Metric context
    metric_name: Optional[str]
    metric_value: Optional[float]
    threshold_value: Optional[float]

    # Timestamps
    fired_at: datetime
    resolved_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[uuid.UUID]

    # Notification tracking
    notifications_sent: int = 0
    last_notification_at: Optional[datetime]

    # Computed
    duration_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class AlertAcknowledgeRequest(BaseModel):
    """Request to acknowledge an alert."""
    comment: Optional[str] = Field(None, max_length=1000)


class AlertBulkAcknowledgeRequest(BaseModel):
    """Request to acknowledge multiple alerts."""
    alert_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)
    comment: Optional[str] = Field(None, max_length=1000)


# =============================================================================
# Notification Channel Schemas
# =============================================================================

class WebhookConfig(BaseModel):
    """Webhook notification channel configuration."""
    url: str = Field(..., description="Webhook URL")
    method: str = Field("POST", pattern="^(POST|PUT)$")
    headers: Dict[str, str] = Field(default_factory=dict)
    auth_type: Optional[str] = Field(None, pattern="^(none|basic|bearer)$")
    auth_token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = Field(30, ge=5, le=120)
    retry_count: int = Field(3, ge=0, le=5)


class SlackConfig(BaseModel):
    """Slack notification channel configuration."""
    webhook_url: str = Field(..., description="Slack webhook URL")
    channel: Optional[str] = Field(None, description="Override channel")
    username: str = Field("Noveris Alerts", description="Bot username")
    icon_emoji: str = Field(":warning:", description="Bot icon emoji")


class EmailConfig(BaseModel):
    """Email notification channel configuration."""
    smtp_host: str
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    use_tls: bool = True
    from_address: str
    to_addresses: List[str]
    cc_addresses: Optional[List[str]] = None


class PagerDutyConfig(BaseModel):
    """PagerDuty notification channel configuration."""
    integration_key: str = Field(..., description="PagerDuty integration key")
    severity_mapping: Dict[str, str] = Field(
        default_factory=lambda: {
            "CRITICAL": "critical",
            "WARNING": "warning",
            "INFO": "info"
        }
    )


class TeamsConfig(BaseModel):
    """Microsoft Teams notification channel configuration."""
    webhook_url: str = Field(..., description="Teams webhook URL")


class NotificationChannelBase(BaseModel):
    """Base notification channel schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    channel_type: NotificationChannelType
    enabled: bool = True
    send_resolved: bool = True
    rate_limit: int = Field(10, ge=1, le=100, description="Max notifications per minute")
    labels: Dict[str, str] = Field(default_factory=dict)


class NotificationChannelCreate(NotificationChannelBase):
    """Schema for creating a notification channel."""
    config: Dict[str, Any] = Field(..., description="Channel-specific configuration")


class NotificationChannelUpdate(BaseModel):
    """Schema for updating a notification channel."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    enabled: Optional[bool] = None
    send_resolved: Optional[bool] = None
    rate_limit: Optional[int] = Field(None, ge=1, le=100)
    config: Optional[Dict[str, Any]] = None
    labels: Optional[Dict[str, str]] = None


class NotificationChannelResponse(NotificationChannelBase):
    """Response schema for notification channel."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    config: Dict[str, Any]  # Sensitive fields masked
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[uuid.UUID]
    last_success_at: Optional[datetime]
    last_failure_at: Optional[datetime]
    failure_count: int = 0

    class Config:
        from_attributes = True


class NotificationChannelTestRequest(BaseModel):
    """Request to test a notification channel."""
    test_message: str = Field("Test alert from Noveris", max_length=500)


class NotificationChannelTestResponse(BaseModel):
    """Response for notification channel test."""
    success: bool
    message: str
    response_time_ms: Optional[int]
    error_details: Optional[str]


# =============================================================================
# Alert Silence Schemas
# =============================================================================

class LabelMatcher(BaseModel):
    """Label matcher for silences."""
    name: str = Field(..., description="Label name to match")
    value: str = Field(..., description="Value to match")
    is_regex: bool = Field(False, description="Treat value as regex")
    is_negative: bool = Field(False, description="Negative match (NOT)")


class AlertSilenceCreate(BaseModel):
    """Schema for creating an alert silence."""
    name: str = Field(..., min_length=1, max_length=255)
    comment: Optional[str] = None
    matchers: List[LabelMatcher] = Field(..., min_items=1)
    starts_at: datetime
    ends_at: datetime

    @validator("ends_at")
    def ends_after_starts(cls, v, values):
        if "starts_at" in values and v <= values["starts_at"]:
            raise ValueError("ends_at must be after starts_at")
        return v


class AlertSilenceUpdate(BaseModel):
    """Schema for updating an alert silence."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    comment: Optional[str] = None
    matchers: Optional[List[LabelMatcher]] = None
    ends_at: Optional[datetime] = None


class AlertSilenceResponse(BaseModel):
    """Response schema for alert silence."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    comment: Optional[str]
    matchers: List[LabelMatcher]
    starts_at: datetime
    ends_at: datetime
    created_at: datetime
    created_by: Optional[uuid.UUID]
    is_active: bool = False

    class Config:
        from_attributes = True


# =============================================================================
# Alert Statistics Schemas
# =============================================================================

class AlertStatistics(BaseModel):
    """Alert statistics response."""
    total_rules: int
    enabled_rules: int
    total_alerts: int
    firing_alerts: int
    resolved_alerts: int
    acknowledged_alerts: int

    by_severity: Dict[str, int]
    by_rule_type: Dict[str, int]
    by_node: List[Dict[str, Any]]  # Top nodes with most alerts

    generated_at: datetime


class AlertTimelineEntry(BaseModel):
    """Single entry in alert timeline."""
    timestamp: datetime
    event_type: str  # fired, resolved, acknowledged
    alert_id: uuid.UUID
    alert_title: str
    severity: AlertSeverity
    node_name: Optional[str]


class AlertTimeline(BaseModel):
    """Alert timeline response."""
    entries: List[AlertTimelineEntry]
    start_time: datetime
    end_time: datetime
    total_count: int
