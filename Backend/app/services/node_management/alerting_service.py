"""
Alerting Service for Node Management.

Business logic for alert rule evaluation, alert management,
and notification delivery.
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alerting import (
    AlertRule, AlertInstance, NotificationChannel, AlertSilence,
    AlertSeverity, AlertState, NotificationChannelType
)
from app.schemas.alerting import (
    AlertRuleCreate, AlertRuleUpdate, AlertRuleResponse,
    AlertInstanceResponse, NotificationChannelCreate, NotificationChannelUpdate,
    AlertSilenceCreate, AlertStatistics
)

logger = structlog.get_logger(__name__)


class AlertingError(Exception):
    """Base alerting error."""
    pass


class AlertRuleNotFoundError(AlertingError):
    """Alert rule not found."""
    pass


class NotificationChannelNotFoundError(AlertingError):
    """Notification channel not found."""
    pass


class NotificationDeliveryError(AlertingError):
    """Notification delivery failed."""
    pass


class AlertingService:
    """Service for managing alerts and notifications."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id

    # =========================================================================
    # Alert Rule Management
    # =========================================================================

    async def create_alert_rule(
        self,
        data: AlertRuleCreate,
        user_id: uuid.UUID
    ) -> AlertRule:
        """Create a new alert rule."""
        rule = AlertRule(
            tenant_id=self.tenant_id,
            name=data.name,
            description=data.description,
            enabled=data.enabled,
            rule_type=data.rule_type.value,
            condition=data.condition,
            severity=AlertSeverity(data.severity.value),
            target_all_nodes=data.target_all_nodes,
            target_node_ids=[str(n) for n in data.target_node_ids] if data.target_node_ids else None,
            target_group_ids=[str(g) for g in data.target_group_ids] if data.target_group_ids else None,
            target_tags=data.target_tags,
            evaluation_interval=data.evaluation_interval,
            for_duration=data.for_duration,
            notification_channel_ids=[str(c) for c in data.notification_channel_ids] if data.notification_channel_ids else None,
            notification_template=data.notification_template,
            labels=data.labels,
            annotations=data.annotations,
            created_by=user_id
        )

        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)

        logger.info(
            "Alert rule created",
            rule_id=str(rule.id),
            name=rule.name,
            rule_type=rule.rule_type
        )

        return rule

    async def get_alert_rule(self, rule_id: uuid.UUID) -> Optional[AlertRule]:
        """Get an alert rule by ID."""
        result = await self.db.execute(
            select(AlertRule)
            .where(AlertRule.id == rule_id)
            .where(AlertRule.tenant_id == self.tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_alert_rules(
        self,
        enabled_only: bool = False,
        rule_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[AlertRule], int]:
        """List alert rules with optional filtering."""
        query = select(AlertRule).where(AlertRule.tenant_id == self.tenant_id)

        if enabled_only:
            query = query.where(AlertRule.enabled == True)
        if rule_type:
            query = query.where(AlertRule.rule_type == rule_type)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        # Get paginated results
        query = query.order_by(AlertRule.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)

        return result.scalars().all(), total

    async def update_alert_rule(
        self,
        rule_id: uuid.UUID,
        data: AlertRuleUpdate,
        user_id: uuid.UUID
    ) -> AlertRule:
        """Update an alert rule."""
        rule = await self.get_alert_rule(rule_id)
        if not rule:
            raise AlertRuleNotFoundError(f"Alert rule {rule_id} not found")

        update_data = data.model_dump(exclude_unset=True)

        # Handle UUID list conversions
        if "target_node_ids" in update_data and update_data["target_node_ids"]:
            update_data["target_node_ids"] = [str(n) for n in update_data["target_node_ids"]]
        if "target_group_ids" in update_data and update_data["target_group_ids"]:
            update_data["target_group_ids"] = [str(g) for g in update_data["target_group_ids"]]
        if "notification_channel_ids" in update_data and update_data["notification_channel_ids"]:
            update_data["notification_channel_ids"] = [str(c) for c in update_data["notification_channel_ids"]]

        for field, value in update_data.items():
            setattr(rule, field, value)

        rule.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(rule)

        logger.info("Alert rule updated", rule_id=str(rule_id))
        return rule

    async def delete_alert_rule(self, rule_id: uuid.UUID) -> bool:
        """Delete an alert rule."""
        rule = await self.get_alert_rule(rule_id)
        if not rule:
            raise AlertRuleNotFoundError(f"Alert rule {rule_id} not found")

        await self.db.delete(rule)
        await self.db.commit()

        logger.info("Alert rule deleted", rule_id=str(rule_id))
        return True

    # =========================================================================
    # Alert Instance Management
    # =========================================================================

    async def create_alert_instance(
        self,
        rule: AlertRule,
        node_id: Optional[uuid.UUID] = None,
        node_name: Optional[str] = None,
        metric_name: Optional[str] = None,
        metric_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
        labels: Optional[Dict] = None,
        annotations: Optional[Dict] = None
    ) -> AlertInstance:
        """Create a new alert instance."""
        # Generate fingerprint for deduplication
        fingerprint_data = f"{rule.id}:{node_id}:{metric_name}"
        fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

        # Check for existing firing alert with same fingerprint
        existing = await self.db.execute(
            select(AlertInstance)
            .where(AlertInstance.tenant_id == self.tenant_id)
            .where(AlertInstance.fingerprint == fingerprint)
            .where(AlertInstance.state == AlertState.FIRING)
        )
        if existing.scalar_one_or_none():
            logger.debug("Alert already firing", fingerprint=fingerprint)
            return None

        # Build title and message
        title = f"[{rule.severity.value}] {rule.name}"
        if node_name:
            title += f" - {node_name}"

        message = rule.description or ""
        if metric_name and metric_value is not None:
            message += f"\nMetric: {metric_name} = {metric_value}"
            if threshold_value is not None:
                message += f" (threshold: {threshold_value})"

        alert = AlertInstance(
            tenant_id=self.tenant_id,
            rule_id=rule.id,
            fingerprint=fingerprint,
            state=AlertState.FIRING,
            severity=rule.severity,
            node_id=node_id,
            node_name=node_name,
            title=title,
            message=message,
            labels=labels or rule.labels,
            annotations=annotations or rule.annotations,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold_value=threshold_value,
            fired_at=datetime.utcnow()
        )

        self.db.add(alert)
        await self.db.commit()
        await self.db.refresh(alert)

        logger.info(
            "Alert fired",
            alert_id=str(alert.id),
            rule_name=rule.name,
            node_name=node_name,
            severity=rule.severity.value
        )

        return alert

    async def resolve_alert(
        self,
        alert_id: uuid.UUID,
        auto_resolved: bool = False
    ) -> AlertInstance:
        """Resolve an alert instance."""
        alert = await self.db.get(AlertInstance, alert_id)
        if not alert or alert.tenant_id != self.tenant_id:
            raise AlertingError(f"Alert {alert_id} not found")

        if alert.state == AlertState.RESOLVED:
            return alert

        alert.state = AlertState.RESOLVED
        alert.resolved_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(alert)

        logger.info(
            "Alert resolved",
            alert_id=str(alert_id),
            auto_resolved=auto_resolved
        )

        return alert

    async def acknowledge_alert(
        self,
        alert_id: uuid.UUID,
        user_id: uuid.UUID,
        comment: Optional[str] = None
    ) -> AlertInstance:
        """Acknowledge an alert instance."""
        alert = await self.db.get(AlertInstance, alert_id)
        if not alert or alert.tenant_id != self.tenant_id:
            raise AlertingError(f"Alert {alert_id} not found")

        alert.state = AlertState.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user_id

        if comment:
            annotations = alert.annotations or {}
            annotations["acknowledge_comment"] = comment
            alert.annotations = annotations

        await self.db.commit()
        await self.db.refresh(alert)

        logger.info(
            "Alert acknowledged",
            alert_id=str(alert_id),
            user_id=str(user_id)
        )

        return alert

    async def list_alerts(
        self,
        state: Optional[AlertState] = None,
        severity: Optional[AlertSeverity] = None,
        rule_id: Optional[uuid.UUID] = None,
        node_id: Optional[uuid.UUID] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[AlertInstance], int]:
        """List alert instances with filtering."""
        query = select(AlertInstance).where(AlertInstance.tenant_id == self.tenant_id)

        if state:
            query = query.where(AlertInstance.state == state)
        if severity:
            query = query.where(AlertInstance.severity == severity)
        if rule_id:
            query = query.where(AlertInstance.rule_id == rule_id)
        if node_id:
            query = query.where(AlertInstance.node_id == node_id)
        if since:
            query = query.where(AlertInstance.fired_at >= since)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        # Get paginated results
        query = query.order_by(AlertInstance.fired_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)

        return result.scalars().all(), total

    async def get_alert_statistics(self) -> AlertStatistics:
        """Get alert statistics for the tenant."""
        # Count rules
        total_rules = (await self.db.execute(
            select(func.count()).where(AlertRule.tenant_id == self.tenant_id)
        )).scalar()

        enabled_rules = (await self.db.execute(
            select(func.count())
            .where(AlertRule.tenant_id == self.tenant_id)
            .where(AlertRule.enabled == True)
        )).scalar()

        # Count alerts by state
        alert_counts = {}
        for state in AlertState:
            count = (await self.db.execute(
                select(func.count())
                .where(AlertInstance.tenant_id == self.tenant_id)
                .where(AlertInstance.state == state)
            )).scalar()
            alert_counts[state.value.lower()] = count

        # Count by severity
        severity_counts = {}
        for sev in AlertSeverity:
            count = (await self.db.execute(
                select(func.count())
                .where(AlertInstance.tenant_id == self.tenant_id)
                .where(AlertInstance.severity == sev)
                .where(AlertInstance.state == AlertState.FIRING)
            )).scalar()
            severity_counts[sev.value] = count

        return AlertStatistics(
            total_rules=total_rules,
            enabled_rules=enabled_rules,
            total_alerts=sum(alert_counts.values()),
            firing_alerts=alert_counts.get("firing", 0),
            resolved_alerts=alert_counts.get("resolved", 0),
            acknowledged_alerts=alert_counts.get("acknowledged", 0),
            by_severity=severity_counts,
            by_rule_type={},  # Would need aggregation
            by_node=[],
            generated_at=datetime.utcnow()
        )

    # =========================================================================
    # Notification Channel Management
    # =========================================================================

    async def create_notification_channel(
        self,
        data: NotificationChannelCreate,
        user_id: uuid.UUID
    ) -> NotificationChannel:
        """Create a notification channel."""
        channel = NotificationChannel(
            tenant_id=self.tenant_id,
            name=data.name,
            description=data.description,
            channel_type=NotificationChannelType(data.channel_type.value),
            enabled=data.enabled,
            config=data.config,
            send_resolved=data.send_resolved,
            rate_limit=data.rate_limit,
            labels=data.labels,
            created_by=user_id
        )

        self.db.add(channel)
        await self.db.commit()
        await self.db.refresh(channel)

        logger.info(
            "Notification channel created",
            channel_id=str(channel.id),
            name=channel.name,
            type=channel.channel_type.value
        )

        return channel

    async def get_notification_channel(self, channel_id: uuid.UUID) -> Optional[NotificationChannel]:
        """Get a notification channel by ID."""
        result = await self.db.execute(
            select(NotificationChannel)
            .where(NotificationChannel.id == channel_id)
            .where(NotificationChannel.tenant_id == self.tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_notification_channels(
        self,
        enabled_only: bool = False,
        channel_type: Optional[NotificationChannelType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[NotificationChannel], int]:
        """List notification channels."""
        query = select(NotificationChannel).where(
            NotificationChannel.tenant_id == self.tenant_id
        )

        if enabled_only:
            query = query.where(NotificationChannel.enabled == True)
        if channel_type:
            query = query.where(NotificationChannel.channel_type == channel_type)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        query = query.order_by(NotificationChannel.name).offset(offset).limit(limit)
        result = await self.db.execute(query)

        return result.scalars().all(), total

    async def update_notification_channel(
        self,
        channel_id: uuid.UUID,
        data: NotificationChannelUpdate
    ) -> NotificationChannel:
        """Update a notification channel."""
        channel = await self.get_notification_channel(channel_id)
        if not channel:
            raise NotificationChannelNotFoundError(f"Channel {channel_id} not found")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(channel, field, value)

        channel.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(channel)

        logger.info("Notification channel updated", channel_id=str(channel_id))
        return channel

    async def delete_notification_channel(self, channel_id: uuid.UUID) -> bool:
        """Delete a notification channel."""
        channel = await self.get_notification_channel(channel_id)
        if not channel:
            raise NotificationChannelNotFoundError(f"Channel {channel_id} not found")

        await self.db.delete(channel)
        await self.db.commit()

        logger.info("Notification channel deleted", channel_id=str(channel_id))
        return True

    async def test_notification_channel(
        self,
        channel_id: uuid.UUID,
        test_message: str
    ) -> Dict[str, Any]:
        """Test a notification channel."""
        channel = await self.get_notification_channel(channel_id)
        if not channel:
            raise NotificationChannelNotFoundError(f"Channel {channel_id} not found")

        start_time = datetime.utcnow()

        try:
            await self._send_notification(
                channel,
                title="Test Alert",
                message=test_message,
                severity=AlertSeverity.INFO,
                is_test=True
            )

            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Update success tracking
            channel.last_success_at = datetime.utcnow()
            channel.failure_count = 0
            await self.db.commit()

            return {
                "success": True,
                "message": "Test notification sent successfully",
                "response_time_ms": elapsed_ms,
                "error_details": None
            }

        except Exception as e:
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Update failure tracking
            channel.last_failure_at = datetime.utcnow()
            channel.failure_count = (channel.failure_count or 0) + 1
            await self.db.commit()

            return {
                "success": False,
                "message": "Test notification failed",
                "response_time_ms": elapsed_ms,
                "error_details": str(e)
            }

    # =========================================================================
    # Notification Delivery
    # =========================================================================

    async def send_alert_notification(
        self,
        alert: AlertInstance,
        is_resolved: bool = False
    ) -> int:
        """Send notifications for an alert to all configured channels."""
        rule = await self.get_alert_rule(alert.rule_id)
        if not rule or not rule.notification_channel_ids:
            return 0

        sent_count = 0

        for channel_id_str in rule.notification_channel_ids:
            try:
                channel_id = uuid.UUID(channel_id_str)
                channel = await self.get_notification_channel(channel_id)

                if not channel or not channel.enabled:
                    continue

                if is_resolved and not channel.send_resolved:
                    continue

                await self._send_notification(
                    channel,
                    title=f"{'[RESOLVED] ' if is_resolved else ''}{alert.title}",
                    message=alert.message,
                    severity=alert.severity,
                    alert=alert
                )

                sent_count += 1

            except Exception as e:
                logger.error(
                    "Failed to send notification",
                    channel_id=channel_id_str,
                    alert_id=str(alert.id),
                    error=str(e)
                )

        # Update alert notification tracking
        alert.notifications_sent = (alert.notifications_sent or 0) + sent_count
        alert.last_notification_at = datetime.utcnow()
        await self.db.commit()

        return sent_count

    async def _send_notification(
        self,
        channel: NotificationChannel,
        title: str,
        message: str,
        severity: AlertSeverity,
        alert: Optional[AlertInstance] = None,
        is_test: bool = False
    ):
        """Send notification to a specific channel."""
        config = channel.config

        if channel.channel_type == NotificationChannelType.WEBHOOK:
            await self._send_webhook_notification(config, title, message, severity, alert)
        elif channel.channel_type == NotificationChannelType.SLACK:
            await self._send_slack_notification(config, title, message, severity, alert)
        elif channel.channel_type == NotificationChannelType.PAGERDUTY:
            await self._send_pagerduty_notification(config, title, message, severity, alert)
        elif channel.channel_type == NotificationChannelType.TEAMS:
            await self._send_teams_notification(config, title, message, severity, alert)
        else:
            raise NotificationDeliveryError(f"Unsupported channel type: {channel.channel_type}")

    async def _send_webhook_notification(
        self,
        config: Dict,
        title: str,
        message: str,
        severity: AlertSeverity,
        alert: Optional[AlertInstance] = None
    ):
        """Send webhook notification."""
        url = config.get("url")
        method = config.get("method", "POST")
        headers = config.get("headers", {})
        timeout = config.get("timeout", 30)

        # Build payload
        payload = {
            "title": title,
            "message": message,
            "severity": severity.value,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "noveris"
        }

        if alert:
            payload["alert"] = {
                "id": str(alert.id),
                "state": alert.state.value,
                "node_id": str(alert.node_id) if alert.node_id else None,
                "node_name": alert.node_name,
                "fired_at": alert.fired_at.isoformat(),
                "labels": alert.labels,
                "metric_name": alert.metric_name,
                "metric_value": alert.metric_value
            }

        # Add auth
        auth_type = config.get("auth_type", "none")
        if auth_type == "bearer" and config.get("auth_token"):
            headers["Authorization"] = f"Bearer {config['auth_token']}"
        elif auth_type == "basic" and config.get("username"):
            import base64
            credentials = f"{config['username']}:{config.get('password', '')}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()

    async def _send_slack_notification(
        self,
        config: Dict,
        title: str,
        message: str,
        severity: AlertSeverity,
        alert: Optional[AlertInstance] = None
    ):
        """Send Slack notification."""
        webhook_url = config.get("webhook_url")
        username = config.get("username", "Noveris Alerts")
        icon_emoji = config.get("icon_emoji", ":warning:")

        # Severity colors
        color_map = {
            AlertSeverity.CRITICAL: "#FF0000",
            AlertSeverity.WARNING: "#FFA500",
            AlertSeverity.INFO: "#0000FF"
        }

        payload = {
            "username": username,
            "icon_emoji": icon_emoji,
            "attachments": [{
                "color": color_map.get(severity, "#808080"),
                "title": title,
                "text": message,
                "footer": "Noveris Alert System",
                "ts": int(datetime.utcnow().timestamp())
            }]
        }

        if config.get("channel"):
            payload["channel"] = config["channel"]

        if alert and alert.node_name:
            payload["attachments"][0]["fields"] = [
                {"title": "Node", "value": alert.node_name, "short": True},
                {"title": "Severity", "value": severity.value, "short": True}
            ]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()

    async def _send_pagerduty_notification(
        self,
        config: Dict,
        title: str,
        message: str,
        severity: AlertSeverity,
        alert: Optional[AlertInstance] = None
    ):
        """Send PagerDuty notification."""
        integration_key = config.get("integration_key")
        severity_mapping = config.get("severity_mapping", {})

        pd_severity = severity_mapping.get(severity.value, "warning")

        payload = {
            "routing_key": integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": title,
                "source": "noveris",
                "severity": pd_severity,
                "custom_details": {
                    "message": message
                }
            }
        }

        if alert:
            payload["dedup_key"] = alert.fingerprint
            payload["payload"]["custom_details"]["node_name"] = alert.node_name
            payload["payload"]["custom_details"]["alert_id"] = str(alert.id)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload
            )
            response.raise_for_status()

    async def _send_teams_notification(
        self,
        config: Dict,
        title: str,
        message: str,
        severity: AlertSeverity,
        alert: Optional[AlertInstance] = None
    ):
        """Send Microsoft Teams notification."""
        webhook_url = config.get("webhook_url")

        # Teams card colors
        color_map = {
            AlertSeverity.CRITICAL: "FF0000",
            AlertSeverity.WARNING: "FFA500",
            AlertSeverity.INFO: "0078D7"
        }

        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color_map.get(severity, "808080"),
            "summary": title,
            "sections": [{
                "activityTitle": title,
                "facts": [
                    {"name": "Severity", "value": severity.value},
                    {"name": "Time", "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}
                ],
                "text": message
            }]
        }

        if alert and alert.node_name:
            payload["sections"][0]["facts"].insert(0, {
                "name": "Node",
                "value": alert.node_name
            })

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()


# Dependency injection helper
async def get_alerting_service(
    db: AsyncSession,
    tenant_id: uuid.UUID
) -> AlertingService:
    """Get AlertingService instance."""
    return AlertingService(db, tenant_id)
