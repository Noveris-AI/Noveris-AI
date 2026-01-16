"""
Alerting Models for Node Management.

Database models for alert rules, alert instances, and notification channels.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


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


class NotificationChannelType(str, Enum):
    """Notification channel types."""
    WEBHOOK = "WEBHOOK"
    EMAIL = "EMAIL"
    SLACK = "SLACK"
    PAGERDUTY = "PAGERDUTY"
    TEAMS = "TEAMS"


class AlertRule(Base):
    """Alert rule definition."""
    __tablename__ = "alert_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Rule identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)

    # Rule configuration
    rule_type = Column(String(50), nullable=False)  # node_status, metric_threshold, job_failure
    condition = Column(JSONB, nullable=False)  # Condition configuration
    severity = Column(SQLEnum(AlertSeverity), default=AlertSeverity.WARNING, nullable=False)

    # Targeting
    target_all_nodes = Column(Boolean, default=False)
    target_node_ids = Column(JSONB, nullable=True)  # List of node UUIDs
    target_group_ids = Column(JSONB, nullable=True)  # List of group UUIDs
    target_tags = Column(JSONB, nullable=True)  # List of tags

    # Evaluation settings
    evaluation_interval = Column(Integer, default=60)  # seconds
    for_duration = Column(Integer, default=300)  # seconds before firing

    # Notification
    notification_channel_ids = Column(JSONB, nullable=True)  # List of channel UUIDs
    notification_template = Column(Text, nullable=True)

    # Metadata
    labels = Column(JSONB, default=dict)
    annotations = Column(JSONB, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    alerts = relationship("AlertInstance", back_populates="rule", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_alert_rules_tenant_enabled", "tenant_id", "enabled"),
    )


class AlertInstance(Base):
    """Active or historical alert instance."""
    __tablename__ = "alert_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False)

    # Alert identification
    fingerprint = Column(String(64), nullable=False)  # Unique identifier for deduplication
    state = Column(SQLEnum(AlertState), default=AlertState.FIRING, nullable=False)
    severity = Column(SQLEnum(AlertSeverity), nullable=False)

    # Context
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True)
    node_name = Column(String(255), nullable=True)
    group_id = Column(UUID(as_uuid=True), nullable=True)

    # Alert details
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=True)
    labels = Column(JSONB, default=dict)
    annotations = Column(JSONB, default=dict)

    # Metric context (for metric-based alerts)
    metric_name = Column(String(255), nullable=True)
    metric_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)

    # Timestamps
    fired_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(UUID(as_uuid=True), nullable=True)

    # Notification tracking
    notifications_sent = Column(Integer, default=0)
    last_notification_at = Column(DateTime, nullable=True)

    # Relationships
    rule = relationship("AlertRule", back_populates="alerts")

    __table_args__ = (
        Index("ix_alert_instances_tenant_state", "tenant_id", "state"),
        Index("ix_alert_instances_fingerprint", "tenant_id", "fingerprint"),
        Index("ix_alert_instances_node", "node_id"),
        Index("ix_alert_instances_fired_at", "fired_at"),
    )


class NotificationChannel(Base):
    """Notification channel configuration."""
    __tablename__ = "notification_channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Channel identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    channel_type = Column(SQLEnum(NotificationChannelType), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    # Channel configuration (encrypted sensitive data)
    config = Column(JSONB, nullable=False)  # Type-specific config

    # Settings
    send_resolved = Column(Boolean, default=True)  # Send resolution notifications
    rate_limit = Column(Integer, default=10)  # Max notifications per minute

    # Metadata
    labels = Column(JSONB, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Status tracking
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_notification_channels_tenant_type", "tenant_id", "channel_type"),
    )


class AlertSilence(Base):
    """Alert silence/mute rule."""
    __tablename__ = "alert_silences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Silence identification
    name = Column(String(255), nullable=False)
    comment = Column(Text, nullable=True)

    # Matching criteria
    matchers = Column(JSONB, nullable=False)  # Label matchers

    # Time window
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_alert_silences_tenant_time", "tenant_id", "starts_at", "ends_at"),
    )
