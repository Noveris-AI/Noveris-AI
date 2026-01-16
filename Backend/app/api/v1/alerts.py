"""
Alerting API Endpoints.

REST API for managing alert rules, alert instances, and notification channels.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.authz.dependencies import RequirePermission
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_tenant_id

from app.schemas.alerting import (
    AlertRuleCreate, AlertRuleUpdate, AlertRuleResponse,
    AlertInstanceResponse, AlertAcknowledgeRequest, AlertBulkAcknowledgeRequest,
    NotificationChannelCreate, NotificationChannelUpdate, NotificationChannelResponse,
    NotificationChannelTestRequest, NotificationChannelTestResponse,
    AlertSilenceCreate, AlertSilenceUpdate, AlertSilenceResponse,
    AlertStatistics, AlertSeverity, AlertState, AlertRuleType, NotificationChannelType
)
from app.services.node_management.alerting_service import (
    AlertingService, AlertRuleNotFoundError, NotificationChannelNotFoundError
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerting"])


# =============================================================================
# Dependencies
# =============================================================================

async def get_alerting_service(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id)
) -> AlertingService:
    """Get AlertingService instance."""
    return AlertingService(db, tenant_id)


# =============================================================================
# Alert Rule Endpoints
# =============================================================================

@router.post(
    "/rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission("node.alert.create"))],
)
async def create_alert_rule(
    data: AlertRuleCreate,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Create a new alert rule.

    Alert rules define conditions that trigger alerts when met.

    **Rule Types:**
    - `node_status`: Alert when node status changes to specified states
    - `metric_threshold`: Alert when a metric exceeds a threshold
    - `job_failure`: Alert on job failures
    - `connectivity`: Alert on connectivity issues

    **Example condition for metric_threshold:**
    ```json
    {
        "metric_name": "cpu_usage",
        "operator": "gt",
        "threshold": 90
    }
    ```
    """
    rule = await service.create_alert_rule(
        data,
        uuid.UUID(current_user.user_id)
    )

    return AlertRuleResponse(
        id=rule.id,
        tenant_id=rule.tenant_id,
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        rule_type=AlertRuleType(rule.rule_type),
        condition=rule.condition,
        severity=AlertSeverity(rule.severity.value),
        target_all_nodes=rule.target_all_nodes,
        target_node_ids=[uuid.UUID(n) for n in rule.target_node_ids] if rule.target_node_ids else None,
        target_group_ids=[uuid.UUID(g) for g in rule.target_group_ids] if rule.target_group_ids else None,
        target_tags=rule.target_tags,
        evaluation_interval=rule.evaluation_interval,
        for_duration=rule.for_duration,
        notification_channel_ids=[uuid.UUID(c) for c in rule.notification_channel_ids] if rule.notification_channel_ids else None,
        notification_template=rule.notification_template,
        labels=rule.labels or {},
        annotations=rule.annotations or {},
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        created_by=rule.created_by,
        active_alerts_count=0
    )


@router.get(
    "/rules",
    response_model=Dict[str, Any],
    dependencies=[Depends(RequirePermission("node.alert.view"))],
)
async def list_alert_rules(
    enabled_only: bool = Query(False, description="Only show enabled rules"),
    rule_type: Optional[str] = Query(None, description="Filter by rule type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """List alert rules with optional filtering."""
    rules, total = await service.list_alert_rules(
        enabled_only=enabled_only,
        rule_type=rule_type,
        limit=limit,
        offset=offset
    )

    return {
        "items": [
            AlertRuleResponse(
                id=r.id,
                tenant_id=r.tenant_id,
                name=r.name,
                description=r.description,
                enabled=r.enabled,
                rule_type=AlertRuleType(r.rule_type),
                condition=r.condition,
                severity=AlertSeverity(r.severity.value),
                target_all_nodes=r.target_all_nodes,
                target_node_ids=[uuid.UUID(n) for n in r.target_node_ids] if r.target_node_ids else None,
                target_group_ids=[uuid.UUID(g) for g in r.target_group_ids] if r.target_group_ids else None,
                target_tags=r.target_tags,
                evaluation_interval=r.evaluation_interval,
                for_duration=r.for_duration,
                notification_channel_ids=[uuid.UUID(c) for c in r.notification_channel_ids] if r.notification_channel_ids else None,
                notification_template=r.notification_template,
                labels=r.labels or {},
                annotations=r.annotations or {},
                created_at=r.created_at,
                updated_at=r.updated_at,
                created_by=r.created_by,
                active_alerts_count=0
            )
            for r in rules
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get(
    "/rules/{rule_id}",
    response_model=AlertRuleResponse,
    dependencies=[Depends(RequirePermission("node.alert.view"))],
)
async def get_alert_rule(
    rule_id: uuid.UUID,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get an alert rule by ID."""
    rule = await service.get_alert_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")

    return AlertRuleResponse(
        id=rule.id,
        tenant_id=rule.tenant_id,
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        rule_type=AlertRuleType(rule.rule_type),
        condition=rule.condition,
        severity=AlertSeverity(rule.severity.value),
        target_all_nodes=rule.target_all_nodes,
        target_node_ids=[uuid.UUID(n) for n in rule.target_node_ids] if rule.target_node_ids else None,
        target_group_ids=[uuid.UUID(g) for g in rule.target_group_ids] if rule.target_group_ids else None,
        target_tags=rule.target_tags,
        evaluation_interval=rule.evaluation_interval,
        for_duration=rule.for_duration,
        notification_channel_ids=[uuid.UUID(c) for c in rule.notification_channel_ids] if rule.notification_channel_ids else None,
        notification_template=rule.notification_template,
        labels=rule.labels or {},
        annotations=rule.annotations or {},
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        created_by=rule.created_by,
        active_alerts_count=0
    )


@router.put(
    "/rules/{rule_id}",
    response_model=AlertRuleResponse,
    dependencies=[Depends(RequirePermission("node.alert.update"))],
)
async def update_alert_rule(
    rule_id: uuid.UUID,
    data: AlertRuleUpdate,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Update an alert rule."""
    try:
        rule = await service.update_alert_rule(
            rule_id,
            data,
            uuid.UUID(current_user.user_id)
        )
    except AlertRuleNotFoundError:
        raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")

    return AlertRuleResponse(
        id=rule.id,
        tenant_id=rule.tenant_id,
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        rule_type=AlertRuleType(rule.rule_type),
        condition=rule.condition,
        severity=AlertSeverity(rule.severity.value),
        target_all_nodes=rule.target_all_nodes,
        target_node_ids=[uuid.UUID(n) for n in rule.target_node_ids] if rule.target_node_ids else None,
        target_group_ids=[uuid.UUID(g) for g in rule.target_group_ids] if rule.target_group_ids else None,
        target_tags=rule.target_tags,
        evaluation_interval=rule.evaluation_interval,
        for_duration=rule.for_duration,
        notification_channel_ids=[uuid.UUID(c) for c in rule.notification_channel_ids] if rule.notification_channel_ids else None,
        notification_template=rule.notification_template,
        labels=rule.labels or {},
        annotations=rule.annotations or {},
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        created_by=rule.created_by,
        active_alerts_count=0
    )


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission("node.alert.delete"))],
)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Delete an alert rule."""
    try:
        await service.delete_alert_rule(rule_id)
    except AlertRuleNotFoundError:
        raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")


@router.post(
    "/rules/{rule_id}:enable",
    response_model=AlertRuleResponse,
    dependencies=[Depends(RequirePermission("node.alert.update"))],
)
async def enable_alert_rule(
    rule_id: uuid.UUID,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Enable an alert rule."""
    try:
        rule = await service.update_alert_rule(
            rule_id,
            AlertRuleUpdate(enabled=True),
            uuid.UUID(current_user.user_id)
        )
    except AlertRuleNotFoundError:
        raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")

    return await get_alert_rule(rule_id, service, current_user)


@router.post(
    "/rules/{rule_id}:disable",
    response_model=AlertRuleResponse,
    dependencies=[Depends(RequirePermission("node.alert.update"))],
)
async def disable_alert_rule(
    rule_id: uuid.UUID,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Disable an alert rule."""
    try:
        rule = await service.update_alert_rule(
            rule_id,
            AlertRuleUpdate(enabled=False),
            uuid.UUID(current_user.user_id)
        )
    except AlertRuleNotFoundError:
        raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")

    return await get_alert_rule(rule_id, service, current_user)


# =============================================================================
# Alert Instance Endpoints
# =============================================================================

@router.get(
    "",
    response_model=Dict[str, Any],
    dependencies=[Depends(RequirePermission("node.alert.view"))],
)
async def list_alerts(
    state: Optional[str] = Query(None, description="Filter by state (FIRING, RESOLVED, ACKNOWLEDGED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, WARNING, INFO)"),
    rule_id: Optional[uuid.UUID] = Query(None, description="Filter by rule ID"),
    node_id: Optional[uuid.UUID] = Query(None, description="Filter by node ID"),
    hours: int = Query(24, ge=1, le=720, description="Show alerts from last N hours"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    List alert instances.

    Returns alerts matching the specified filters.
    """
    state_enum = AlertState(state) if state else None
    severity_enum = AlertSeverity(severity) if severity else None
    since = datetime.utcnow() - timedelta(hours=hours)

    alerts, total = await service.list_alerts(
        state=state_enum,
        severity=severity_enum,
        rule_id=rule_id,
        node_id=node_id,
        since=since,
        limit=limit,
        offset=offset
    )

    items = []
    for a in alerts:
        duration = None
        if a.resolved_at and a.fired_at:
            duration = int((a.resolved_at - a.fired_at).total_seconds())
        elif a.fired_at:
            duration = int((datetime.utcnow() - a.fired_at).total_seconds())

        items.append(AlertInstanceResponse(
            id=a.id,
            tenant_id=a.tenant_id,
            rule_id=a.rule_id,
            fingerprint=a.fingerprint,
            title=a.title,
            message=a.message,
            severity=AlertSeverity(a.severity.value),
            state=AlertState(a.state.value),
            node_id=a.node_id,
            node_name=a.node_name,
            group_id=a.group_id,
            labels=a.labels or {},
            annotations=a.annotations or {},
            metric_name=a.metric_name,
            metric_value=a.metric_value,
            threshold_value=a.threshold_value,
            fired_at=a.fired_at,
            resolved_at=a.resolved_at,
            acknowledged_at=a.acknowledged_at,
            acknowledged_by=a.acknowledged_by,
            notifications_sent=a.notifications_sent or 0,
            last_notification_at=a.last_notification_at,
            duration_seconds=duration
        ))

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get(
    "/{alert_id}",
    response_model=AlertInstanceResponse,
    dependencies=[Depends(RequirePermission("node.alert.view"))],
)
async def get_alert(
    alert_id: uuid.UUID,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get an alert instance by ID."""
    alerts, _ = await service.list_alerts(limit=1, offset=0)

    # Direct lookup would be better, simplified here
    for a in alerts:
        if a.id == alert_id:
            duration = None
            if a.resolved_at and a.fired_at:
                duration = int((a.resolved_at - a.fired_at).total_seconds())
            elif a.fired_at:
                duration = int((datetime.utcnow() - a.fired_at).total_seconds())

            return AlertInstanceResponse(
                id=a.id,
                tenant_id=a.tenant_id,
                rule_id=a.rule_id,
                fingerprint=a.fingerprint,
                title=a.title,
                message=a.message,
                severity=AlertSeverity(a.severity.value),
                state=AlertState(a.state.value),
                node_id=a.node_id,
                node_name=a.node_name,
                group_id=a.group_id,
                labels=a.labels or {},
                annotations=a.annotations or {},
                metric_name=a.metric_name,
                metric_value=a.metric_value,
                threshold_value=a.threshold_value,
                fired_at=a.fired_at,
                resolved_at=a.resolved_at,
                acknowledged_at=a.acknowledged_at,
                acknowledged_by=a.acknowledged_by,
                notifications_sent=a.notifications_sent or 0,
                last_notification_at=a.last_notification_at,
                duration_seconds=duration
            )

    raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")


@router.post(
    "/{alert_id}:acknowledge",
    response_model=AlertInstanceResponse,
    dependencies=[Depends(RequirePermission("node.alert.update"))],
)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    data: AlertAcknowledgeRequest,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Acknowledge an alert."""
    try:
        alert = await service.acknowledge_alert(
            alert_id,
            uuid.UUID(current_user.user_id),
            data.comment
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    return await get_alert(alert_id, service, current_user)


@router.post(
    "/{alert_id}:resolve",
    response_model=AlertInstanceResponse,
    dependencies=[Depends(RequirePermission("node.alert.update"))],
)
async def resolve_alert(
    alert_id: uuid.UUID,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Manually resolve an alert."""
    try:
        alert = await service.resolve_alert(alert_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    return await get_alert(alert_id, service, current_user)


@router.post(
    ":acknowledge-bulk",
    dependencies=[Depends(RequirePermission("node.alert.update"))],
)
async def bulk_acknowledge_alerts(
    data: AlertBulkAcknowledgeRequest,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Acknowledge multiple alerts at once."""
    results = []
    success_count = 0

    for alert_id in data.alert_ids:
        try:
            await service.acknowledge_alert(
                alert_id,
                uuid.UUID(current_user.user_id),
                data.comment
            )
            results.append({"alert_id": str(alert_id), "status": "success"})
            success_count += 1
        except Exception as e:
            results.append({"alert_id": str(alert_id), "status": "failed", "error": str(e)})

    return {
        "total_count": len(data.alert_ids),
        "success_count": success_count,
        "failed_count": len(data.alert_ids) - success_count,
        "results": results
    }


# =============================================================================
# Statistics Endpoints
# =============================================================================

@router.get(
    "/statistics",
    response_model=AlertStatistics,
    dependencies=[Depends(RequirePermission("node.alert.view"))],
)
async def get_alert_statistics(
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get alert statistics for the tenant."""
    return await service.get_alert_statistics()


# =============================================================================
# Notification Channel Endpoints
# =============================================================================

channels_router = APIRouter(prefix="/channels", tags=["Notification Channels"])


@channels_router.post(
    "",
    response_model=NotificationChannelResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission("node.alert.create"))],
)
async def create_notification_channel(
    data: NotificationChannelCreate,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Create a notification channel.

    **Channel Types:**
    - `WEBHOOK`: Generic HTTP webhook
    - `SLACK`: Slack incoming webhook
    - `PAGERDUTY`: PagerDuty integration
    - `TEAMS`: Microsoft Teams webhook
    - `EMAIL`: Email notifications (SMTP)

    **Example Webhook config:**
    ```json
    {
        "url": "https://hooks.example.com/alerts",
        "method": "POST",
        "auth_type": "bearer",
        "auth_token": "secret-token"
    }
    ```
    """
    channel = await service.create_notification_channel(
        data,
        uuid.UUID(current_user.user_id)
    )

    # Mask sensitive config fields
    masked_config = _mask_sensitive_config(channel.config, channel.channel_type.value)

    return NotificationChannelResponse(
        id=channel.id,
        tenant_id=channel.tenant_id,
        name=channel.name,
        description=channel.description,
        channel_type=NotificationChannelType(channel.channel_type.value),
        enabled=channel.enabled,
        config=masked_config,
        send_resolved=channel.send_resolved,
        rate_limit=channel.rate_limit,
        labels=channel.labels or {},
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        created_by=channel.created_by,
        last_success_at=channel.last_success_at,
        last_failure_at=channel.last_failure_at,
        failure_count=channel.failure_count or 0
    )


@channels_router.get(
    "",
    response_model=Dict[str, Any],
    dependencies=[Depends(RequirePermission("node.alert.view"))],
)
async def list_notification_channels(
    enabled_only: bool = Query(False),
    channel_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """List notification channels."""
    type_enum = NotificationChannelType(channel_type) if channel_type else None

    channels, total = await service.list_notification_channels(
        enabled_only=enabled_only,
        channel_type=type_enum,
        limit=limit,
        offset=offset
    )

    items = []
    for c in channels:
        masked_config = _mask_sensitive_config(c.config, c.channel_type.value)
        items.append(NotificationChannelResponse(
            id=c.id,
            tenant_id=c.tenant_id,
            name=c.name,
            description=c.description,
            channel_type=NotificationChannelType(c.channel_type.value),
            enabled=c.enabled,
            config=masked_config,
            send_resolved=c.send_resolved,
            rate_limit=c.rate_limit,
            labels=c.labels or {},
            created_at=c.created_at,
            updated_at=c.updated_at,
            created_by=c.created_by,
            last_success_at=c.last_success_at,
            last_failure_at=c.last_failure_at,
            failure_count=c.failure_count or 0
        ))

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@channels_router.get(
    "/{channel_id}",
    response_model=NotificationChannelResponse,
    dependencies=[Depends(RequirePermission("node.alert.view"))],
)
async def get_notification_channel(
    channel_id: uuid.UUID,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get a notification channel by ID."""
    channel = await service.get_notification_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    masked_config = _mask_sensitive_config(channel.config, channel.channel_type.value)

    return NotificationChannelResponse(
        id=channel.id,
        tenant_id=channel.tenant_id,
        name=channel.name,
        description=channel.description,
        channel_type=NotificationChannelType(channel.channel_type.value),
        enabled=channel.enabled,
        config=masked_config,
        send_resolved=channel.send_resolved,
        rate_limit=channel.rate_limit,
        labels=channel.labels or {},
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        created_by=channel.created_by,
        last_success_at=channel.last_success_at,
        last_failure_at=channel.last_failure_at,
        failure_count=channel.failure_count or 0
    )


@channels_router.put(
    "/{channel_id}",
    response_model=NotificationChannelResponse,
    dependencies=[Depends(RequirePermission("node.alert.update"))],
)
async def update_notification_channel(
    channel_id: uuid.UUID,
    data: NotificationChannelUpdate,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Update a notification channel."""
    try:
        channel = await service.update_notification_channel(channel_id, data)
    except NotificationChannelNotFoundError:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    return await get_notification_channel(channel_id, service, current_user)


@channels_router.delete(
    "/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission("node.alert.delete"))],
)
async def delete_notification_channel(
    channel_id: uuid.UUID,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Delete a notification channel."""
    try:
        await service.delete_notification_channel(channel_id)
    except NotificationChannelNotFoundError:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")


@channels_router.post(
    "/{channel_id}:test",
    response_model=NotificationChannelTestResponse,
    dependencies=[Depends(RequirePermission("node.alert.update"))],
)
async def test_notification_channel(
    channel_id: uuid.UUID,
    data: NotificationChannelTestRequest,
    service: AlertingService = Depends(get_alerting_service),
    current_user: Dict = Depends(get_current_user)
):
    """Test a notification channel by sending a test message."""
    try:
        result = await service.test_notification_channel(channel_id, data.test_message)
    except NotificationChannelNotFoundError:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    return NotificationChannelTestResponse(**result)


# =============================================================================
# Helper Functions
# =============================================================================

def _mask_sensitive_config(config: Dict, channel_type: str) -> Dict:
    """Mask sensitive fields in channel configuration."""
    masked = config.copy()

    sensitive_fields = [
        "auth_token", "password", "secret_id", "integration_key",
        "smtp_password", "webhook_url"
    ]

    for field in sensitive_fields:
        if field in masked and masked[field]:
            value = masked[field]
            if len(value) > 8:
                masked[field] = value[:4] + "****" + value[-4:]
            else:
                masked[field] = "****"

    return masked


# Include channels router
router.include_router(channels_router)
