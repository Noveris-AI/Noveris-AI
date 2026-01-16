"""
Monitoring API Routes.

This module provides the FastAPI routes for the monitoring module.
All routes require authentication and respect RBAC permissions.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUserDep
from app.models.user import User
from app.monitoring.models import (
    MonitoringSettings,
    MonitoringTarget,
    MonitoringAdapter,
    MonitoringAlertRule,
    MonitoringEvent,
    MonitoringCostProfile,
    MonitoringBudget,
    TargetType,
    AdapterVendor,
    AdapterMode,
    AlertSeverity,
    EventLevel,
    BudgetScope,
    BudgetWindow,
)
from app.monitoring.schemas import (
    TimeRange,
    HealthStatus,
    OverviewResponse,
    MonitoringSettingsUpdate,
    TargetCreate,
    TargetUpdate,
    AlertRuleCreate,
    AdapterCreate,
    CostProfileCreate,
    BudgetCreate,
    NodeSummary,
    AcceleratorSummary,
    ModelInstanceSummary,
    ActiveAlert,
    AlertAckRequest,
)
from app.monitoring.service import get_monitoring_service, MonitoringService

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# =============================================================================
# Dependencies
# =============================================================================

async def get_service() -> MonitoringService:
    """Get monitoring service instance."""
    return get_monitoring_service()


def get_tenant_id(user: User) -> UUID:
    """Extract tenant ID from user."""
    # In production, this would come from user's tenant association
    # For now, using user's ID as tenant ID for simplicity
    return user.id


# =============================================================================
# Overview Routes
# =============================================================================

@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    range: str = Query("1h", description="Time range (15m, 1h, 6h, 24h, 7d, 30d)"),
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
    service: MonitoringService = Depends(get_service),
):
    """
    Get monitoring overview with dashboard cards.

    Returns aggregated metrics for all monitoring domains in card format.
    """
    tenant_id = get_tenant_id(current_user)
    return await service.get_overview_cards(db, tenant_id, range)


@router.get("/overview/health")
async def get_data_sources_health(
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
    service: MonitoringService = Depends(get_service),
):
    """Check health of all monitoring data sources."""
    tenant_id = get_tenant_id(current_user)
    return await service.check_data_sources_health(db, tenant_id)


# =============================================================================
# Nodes Routes
# =============================================================================

@router.get("/nodes")
async def list_nodes(
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
    service: MonitoringService = Depends(get_service),
):
    """
    List all monitored nodes with their status.

    Returns node summaries including health status and basic metrics.
    """
    tenant_id = get_tenant_id(current_user)
    prom = await service.get_prometheus_client(db, tenant_id)

    if not prom:
        return {"nodes": [], "message": "Prometheus not configured"}

    nodes = []

    try:
        # Get nodes from Prometheus
        result = await prom.query('up{job="node"}')

        if result.status == "success" and result.data.get("result"):
            for item in result.data["result"]:
                labels = item.get("metric", {})
                instance = labels.get("instance", "unknown")
                is_up = float(item["value"][1]) == 1

                nodes.append({
                    "instance": instance,
                    "hostname": labels.get("hostname", instance.split(":")[0]),
                    "status": "ok" if is_up else "critical",
                    "labels": labels,
                })

    except Exception as e:
        return {"nodes": [], "error": str(e)}

    return {"nodes": nodes}


@router.get("/nodes/{node_id}/metrics")
async def get_node_metrics(
    node_id: str,
    range: str = Query("1h", description="Time range"),
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
    service: MonitoringService = Depends(get_service),
):
    """Get detailed metrics for a specific node."""
    tenant_id = get_tenant_id(current_user)
    prom = await service.get_prometheus_client(db, tenant_id)

    if not prom:
        raise HTTPException(status_code=503, detail="Prometheus not configured")

    start, end, step = service._parse_time_range(range)
    metrics = {}

    try:
        # CPU usage
        result = await prom.query_range(
            f'100 - (avg by(instance)(irate(node_cpu_seconds_total{{instance=~"{node_id}.*",mode="idle"}}[5m])) * 100)',
            start, end, step
        )
        if result.status == "success" and result.data.get("result"):
            metrics["cpu"] = result.data["result"]

        # Memory usage
        result = await prom.query_range(
            f'(1 - node_memory_MemAvailable_bytes{{instance=~"{node_id}.*"}} / node_memory_MemTotal_bytes{{instance=~"{node_id}.*"}}) * 100',
            start, end, step
        )
        if result.status == "success" and result.data.get("result"):
            metrics["memory"] = result.data["result"]

        # Disk usage
        result = await prom.query_range(
            f'(1 - node_filesystem_avail_bytes{{instance=~"{node_id}.*",mountpoint="/"}} / node_filesystem_size_bytes{{instance=~"{node_id}.*",mountpoint="/"}}) * 100',
            start, end, step
        )
        if result.status == "success" and result.data.get("result"):
            metrics["disk"] = result.data["result"]

        # Load average
        result = await prom.query_range(
            f'node_load1{{instance=~"{node_id}.*"}}',
            start, end, step
        )
        if result.status == "success" and result.data.get("result"):
            metrics["load"] = result.data["result"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"node_id": node_id, "range": range, "metrics": metrics}


# =============================================================================
# Accelerators Routes
# =============================================================================

@router.get("/accelerators")
async def list_accelerators(
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
    service: MonitoringService = Depends(get_service),
):
    """
    List all GPU/NPU accelerators with their status.

    Returns accelerator summaries including health and utilization.
    """
    tenant_id = get_tenant_id(current_user)
    prom = await service.get_prometheus_client(db, tenant_id)

    if not prom:
        return {"accelerators": [], "message": "Prometheus not configured"}

    accelerators = []

    try:
        # Try NVIDIA first
        result = await prom.query('DCGM_FI_DEV_GPU_TEMP')

        if result.status == "success" and result.data.get("result"):
            for item in result.data["result"]:
                labels = item.get("metric", {})
                accelerators.append({
                    "vendor": "nvidia",
                    "device_id": labels.get("gpu", "0"),
                    "model": labels.get("modelName", "Unknown"),
                    "hostname": labels.get("Hostname", "unknown"),
                    "uuid": labels.get("UUID"),
                    "temperature": float(item["value"][1]),
                })

        # Try Ascend NPU
        result = await prom.query('npu_chip_info_temperature')

        if result.status == "success" and result.data.get("result"):
            for item in result.data["result"]:
                labels = item.get("metric", {})
                accelerators.append({
                    "vendor": "huawei_ascend",
                    "device_id": labels.get("id", "0"),
                    "model": labels.get("name", "Ascend NPU"),
                    "hostname": labels.get("hostname", "unknown"),
                    "temperature": float(item["value"][1]),
                })

    except Exception as e:
        return {"accelerators": [], "error": str(e)}

    return {"accelerators": accelerators}


@router.get("/accelerators/{node_id}/metrics")
async def get_accelerator_metrics(
    node_id: str,
    device: str = Query("0", description="Device ID"),
    range: str = Query("1h", description="Time range"),
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
    service: MonitoringService = Depends(get_service),
):
    """Get detailed metrics for a specific accelerator."""
    tenant_id = get_tenant_id(current_user)
    prom = await service.get_prometheus_client(db, tenant_id)

    if not prom:
        raise HTTPException(status_code=503, detail="Prometheus not configured")

    start, end, step = service._parse_time_range(range)
    metrics = {}

    try:
        # Temperature
        result = await prom.query_range(
            f'DCGM_FI_DEV_GPU_TEMP{{Hostname=~"{node_id}.*",gpu="{device}"}}',
            start, end, step
        )
        if result.status == "success" and result.data.get("result"):
            metrics["temperature"] = result.data["result"]

        # Power
        result = await prom.query_range(
            f'DCGM_FI_DEV_POWER_USAGE{{Hostname=~"{node_id}.*",gpu="{device}"}}',
            start, end, step
        )
        if result.status == "success" and result.data.get("result"):
            metrics["power"] = result.data["result"]

        # Memory used
        result = await prom.query_range(
            f'DCGM_FI_DEV_FB_USED{{Hostname=~"{node_id}.*",gpu="{device}"}}',
            start, end, step
        )
        if result.status == "success" and result.data.get("result"):
            metrics["memory_used"] = result.data["result"]

        # Utilization
        result = await prom.query_range(
            f'DCGM_FI_DEV_GPU_UTIL{{Hostname=~"{node_id}.*",gpu="{device}"}}',
            start, end, step
        )
        if result.status == "success" and result.data.get("result"):
            metrics["utilization"] = result.data["result"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"node_id": node_id, "device": device, "range": range, "metrics": metrics}


@router.get("/accelerators/adapters")
async def list_adapters(
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
):
    """List configured accelerator adapters."""
    tenant_id = get_tenant_id(current_user)

    result = await db.execute(
        select(MonitoringAdapter).where(MonitoringAdapter.tenant_id == tenant_id)
    )
    adapters = result.scalars().all()

    return {
        "adapters": [
            {
                "id": str(a.id),
                "name": a.name,
                "vendor": a.vendor.value,
                "mode": a.mode.value,
                "enabled": a.enabled,
                "last_collection_at": a.last_collection_at,
                "last_collection_status": a.last_collection_status,
            }
            for a in adapters
        ]
    }


@router.post("/accelerators/adapters")
async def create_adapter(
    data: AdapterCreate,
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
):
    """Create a new accelerator adapter."""
    tenant_id = get_tenant_id(current_user)

    adapter = MonitoringAdapter(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        vendor=AdapterVendor(data.vendor),
        mode=AdapterMode(data.mode),
        config=data.config,
        mapping=data.mapping,
        label_mapping=data.label_mapping,
        extra_labels=data.extra_labels,
        created_by=current_user.id,
    )

    db.add(adapter)
    await db.commit()
    await db.refresh(adapter)

    return {"id": str(adapter.id), "message": "Adapter created successfully"}


# =============================================================================
# Gateway Routes
# =============================================================================

@router.get("/gateway/traffic")
async def get_gateway_traffic(
    range: str = Query("1h", description="Time range"),
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
    service: MonitoringService = Depends(get_service),
):
    """Get gateway traffic metrics."""
    tenant_id = get_tenant_id(current_user)
    prom = await service.get_prometheus_client(db, tenant_id)

    if not prom:
        raise HTTPException(status_code=503, detail="Prometheus not configured")

    start, end, step = service._parse_time_range(range)
    metrics = {}

    try:
        # Request rate
        result = await prom.query_range(
            'sum(rate(http_requests_total{job="gateway"}[5m]))',
            start, end, step
        )
        if result.status == "success" and result.data.get("result"):
            metrics["requests_per_second"] = result.data["result"]

        # Error rate
        result = await prom.query_range(
            'sum(rate(http_requests_total{job="gateway",status=~"5.."}[5m])) / sum(rate(http_requests_total{job="gateway"}[5m])) * 100',
            start, end, step
        )
        if result.status == "success" and result.data.get("result"):
            metrics["error_rate"] = result.data["result"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"range": range, "metrics": metrics}


# =============================================================================
# Alerts Routes
# =============================================================================

@router.get("/alerts/active")
async def get_active_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
    service: MonitoringService = Depends(get_service),
):
    """Get active alerts from Alertmanager."""
    tenant_id = get_tenant_id(current_user)
    am = await service.get_alertmanager_client(db, tenant_id)

    if not am:
        return {"alerts": [], "message": "Alertmanager not configured"}

    try:
        labels = {"severity": severity} if severity else None
        result = await am.get_alerts(
            active=True,
            silenced=False,
            inhibited=False,
            filter_labels=labels,
        )

        if result.status == "success":
            return {"alerts": result.data}
        return {"alerts": [], "error": result.error}

    except Exception as e:
        return {"alerts": [], "error": str(e)}


@router.post("/alerts/{fingerprint}/ack")
async def acknowledge_alert(
    fingerprint: str,
    data: AlertAckRequest,
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
    service: MonitoringService = Depends(get_service),
):
    """Acknowledge an alert."""
    tenant_id = get_tenant_id(current_user)

    # Record acknowledgment event
    from app.monitoring.models import EventType, EventLevel

    await service.record_event(
        db=db,
        tenant_id=tenant_id,
        event_type=EventType.ALERT_ACK,
        level=EventLevel.INFO,
        title=f"Alert {fingerprint} acknowledged",
        payload={"note": data.note, "fingerprint": fingerprint},
        source="api",
        triggered_by=current_user.id,
    )

    await db.commit()

    return {"message": "Alert acknowledged", "fingerprint": fingerprint}


# =============================================================================
# Settings Routes
# =============================================================================

@router.get("/settings")
async def get_settings(
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
):
    """Get monitoring settings for the tenant."""
    tenant_id = get_tenant_id(current_user)

    result = await db.execute(
        select(MonitoringSettings).where(MonitoringSettings.tenant_id == tenant_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # Return defaults
        return {
            "prometheus_url": "http://localhost:9090",
            "prometheus_enabled": False,
            "loki_url": "http://localhost:3100",
            "loki_enabled": False,
            "tempo_url": "http://localhost:3200",
            "tempo_enabled": False,
            "alertmanager_url": "http://localhost:9093",
            "alertmanager_enabled": False,
            "enabled_domains": {
                "nodes": True,
                "accelerators": True,
                "models": True,
                "gateway": True,
                "jobs": True,
                "network": True,
                "cost": True,
                "security": True,
            },
            "default_range": "1h",
            "default_mode": "simple",
        }

    return {
        "prometheus_url": settings.prometheus_url,
        "prometheus_enabled": settings.prometheus_enabled,
        "loki_url": settings.loki_url,
        "loki_enabled": settings.loki_enabled,
        "tempo_url": settings.tempo_url,
        "tempo_enabled": settings.tempo_enabled,
        "alertmanager_url": settings.alertmanager_url,
        "alertmanager_enabled": settings.alertmanager_enabled,
        "enabled_domains": settings.enabled_domains,
        "default_range": settings.default_range,
        "default_mode": settings.default_mode,
    }


@router.put("/settings")
async def update_settings(
    data: MonitoringSettingsUpdate,
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
):
    """Update monitoring settings."""
    tenant_id = get_tenant_id(current_user)

    result = await db.execute(
        select(MonitoringSettings).where(MonitoringSettings.tenant_id == tenant_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # Create new settings
        settings = MonitoringSettings(tenant_id=tenant_id)
        db.add(settings)

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(settings, field):
            setattr(settings, field, value)

    await db.commit()

    return {"message": "Settings updated successfully"}


# =============================================================================
# Targets Routes
# =============================================================================

@router.get("/targets")
async def list_targets(
    type: Optional[str] = Query(None, description="Filter by target type"),
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
):
    """List monitoring targets."""
    tenant_id = get_tenant_id(current_user)

    query = select(MonitoringTarget).where(MonitoringTarget.tenant_id == tenant_id)
    if type:
        query = query.where(MonitoringTarget.type == TargetType(type))

    result = await db.execute(query)
    targets = result.scalars().all()

    return {
        "targets": [
            {
                "id": str(t.id),
                "name": t.name,
                "type": t.type.value,
                "scrape_url": t.scrape_url,
                "enabled": t.enabled,
                "last_scrape_at": t.last_scrape_at,
                "last_scrape_status": t.last_scrape_status,
            }
            for t in targets
        ]
    }


@router.post("/targets")
async def create_target(
    data: TargetCreate,
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
):
    """Create a new monitoring target."""
    tenant_id = get_tenant_id(current_user)

    target = MonitoringTarget(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        type=TargetType(data.type),
        scrape_url=data.scrape_url,
        scrape_interval=data.scrape_interval,
        scrape_timeout=data.scrape_timeout,
        metrics_path=data.metrics_path,
        labels=data.labels,
        tls_enabled=data.tls_enabled,
        basic_auth_enabled=data.basic_auth_enabled,
        created_by=current_user.id,
    )

    db.add(target)
    await db.commit()
    await db.refresh(target)

    return {"id": str(target.id), "message": "Target created successfully"}


@router.delete("/targets/{target_id}")
async def delete_target(
    target_id: UUID,
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
):
    """Delete a monitoring target."""
    tenant_id = get_tenant_id(current_user)

    result = await db.execute(
        select(MonitoringTarget).where(
            MonitoringTarget.id == target_id,
            MonitoringTarget.tenant_id == tenant_id,
        )
    )
    target = result.scalar_one_or_none()

    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    await db.delete(target)
    await db.commit()

    return {"message": "Target deleted successfully"}


# =============================================================================
# Events Routes
# =============================================================================

@router.get("/events")
async def list_events(
    type: Optional[str] = Query(None, description="Filter by event type"),
    level: Optional[str] = Query(None, description="Filter by event level"),
    limit: int = Query(100, description="Maximum events to return"),
    offset: int = Query(0, description="Pagination offset"),
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
):
    """List monitoring events."""
    tenant_id = get_tenant_id(current_user)

    query = select(MonitoringEvent).where(
        MonitoringEvent.tenant_id == tenant_id
    ).order_by(MonitoringEvent.created_at.desc())

    if type:
        from app.monitoring.models import EventType
        query = query.where(MonitoringEvent.type == EventType(type))

    if level:
        query = query.where(MonitoringEvent.level == EventLevel(level))

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    return {
        "events": [
            {
                "id": str(e.id),
                "type": e.type.value,
                "level": e.level.value,
                "title": e.title,
                "payload": e.payload,
                "source": e.source,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
        "limit": limit,
        "offset": offset,
    }


# =============================================================================
# Cost Routes
# =============================================================================

@router.get("/cost/summary")
async def get_cost_summary(
    range: str = Query("30d", description="Time range"),
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
):
    """Get cost summary for the tenant."""
    tenant_id = get_tenant_id(current_user)

    # Get budgets to calculate current spending
    result = await db.execute(
        select(MonitoringBudget).where(
            MonitoringBudget.tenant_id == tenant_id,
            MonitoringBudget.enabled == True,
        )
    )
    budgets = result.scalars().all()

    return {
        "total_spending": sum(float(b.current_spending or 0) for b in budgets),
        "total_budget": sum(float(b.limit_amount or 0) for b in budgets),
        "currency": "USD",
        "budgets": [
            {
                "id": str(b.id),
                "name": b.name,
                "scope": b.scope.value,
                "limit": float(b.limit_amount),
                "current": float(b.current_spending or 0),
                "status": b.status,
            }
            for b in budgets
        ],
    }


@router.post("/cost/budget")
async def create_budget(
    data: BudgetCreate,
    current_user: User = Depends(CurrentUserDep),
    db: AsyncSession = Depends(get_db),
):
    """Create a new budget."""
    tenant_id = get_tenant_id(current_user)

    budget = MonitoringBudget(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        scope=BudgetScope(data.scope),
        scope_target=data.scope_target,
        limit_amount=data.limit_amount,
        limit_currency=data.limit_currency,
        window=BudgetWindow(data.window),
        alert_thresholds=data.alert_thresholds,
        notification_config=data.notification_config,
        created_by=current_user.id,
    )

    db.add(budget)
    await db.commit()
    await db.refresh(budget)

    return {"id": str(budget.id), "message": "Budget created successfully"}
