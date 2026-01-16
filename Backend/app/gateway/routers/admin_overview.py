"""
Gateway Control Plane - Overview API.

This module provides overview/statistics endpoint for the gateway dashboard.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, case, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_tenant_id
from app.models.gateway import GatewayRequest, GatewayUpstream


router = APIRouter(prefix="/api/gateway/overview", tags=["gateway-admin"])


# =============================================================================
# Schemas
# =============================================================================

class ModelCount(BaseModel):
    """Model usage count."""
    model: str
    count: int


class UpstreamCount(BaseModel):
    """Upstream usage count."""
    upstream: str
    count: int


class HourlyCount(BaseModel):
    """Hourly request count."""
    hour: str
    count: int


class GatewayOverviewResponse(BaseModel):
    """Gateway overview statistics response."""
    total_requests: int
    total_errors: int
    error_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    total_tokens: int
    total_cost_usd: float
    top_models: List[ModelCount]
    top_upstreams: List[UpstreamCount]
    requests_by_hour: List[HourlyCount]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=GatewayOverviewResponse)
async def get_gateway_overview(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get gateway overview statistics.

    Returns aggregated statistics for the gateway including:
    - Total requests and errors
    - Average and P95 latency
    - Token usage and costs
    - Top models and upstreams
    - Hourly request distribution
    """
    # Parse date range
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            end_dt = datetime.utcnow()
    else:
        end_dt = datetime.utcnow()

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            start_dt = end_dt - timedelta(hours=24)
    else:
        start_dt = end_dt - timedelta(hours=24)

    # Base filter for tenant and date range
    base_filter = and_(
        GatewayRequest.tenant_id == tenant_id,
        GatewayRequest.created_at >= start_dt,
        GatewayRequest.created_at <= end_dt
    )

    # 1. Get aggregate statistics
    stats_query = select(
        func.count(GatewayRequest.id).label('total_requests'),
        func.count(
            case(
                (GatewayRequest.error_type.isnot(None), 1),
                (GatewayRequest.status_code >= 400, 1)
            )
        ).label('total_errors'),
        func.coalesce(func.avg(GatewayRequest.latency_ms), 0).label('avg_latency_ms'),
        func.coalesce(func.sum(GatewayRequest.total_tokens), 0).label('total_tokens'),
        func.coalesce(func.sum(GatewayRequest.cost_usd), 0).label('total_cost_usd'),
    ).where(base_filter)

    stats_result = await db.execute(stats_query)
    stats_row = stats_result.one()

    total_requests = stats_row.total_requests or 0
    total_errors = stats_row.total_errors or 0
    avg_latency_ms = float(stats_row.avg_latency_ms or 0)
    total_tokens = int(stats_row.total_tokens or 0)
    total_cost_usd = float(stats_row.total_cost_usd or 0)

    # Calculate error rate
    error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

    # 2. Calculate P95 latency using percentile_cont
    p95_latency_ms = 0.0
    if total_requests > 0:
        # Use percentile_cont for P95 calculation
        p95_query = select(
            func.percentile_cont(0.95).within_group(
                GatewayRequest.latency_ms
            ).label('p95_latency')
        ).where(
            and_(base_filter, GatewayRequest.latency_ms.isnot(None))
        )
        try:
            p95_result = await db.execute(p95_query)
            p95_row = p95_result.one_or_none()
            if p95_row and p95_row.p95_latency:
                p95_latency_ms = float(p95_row.p95_latency)
        except Exception:
            # Fallback: use simple approximation if percentile_cont not available
            p95_latency_ms = avg_latency_ms * 1.5

    # 3. Get top models
    top_models_query = (
        select(
            GatewayRequest.virtual_model.label('model'),
            func.count(GatewayRequest.id).label('count')
        )
        .where(and_(base_filter, GatewayRequest.virtual_model.isnot(None)))
        .group_by(GatewayRequest.virtual_model)
        .order_by(func.count(GatewayRequest.id).desc())
        .limit(10)
    )
    top_models_result = await db.execute(top_models_query)
    top_models = [
        ModelCount(model=row.model, count=row.count)
        for row in top_models_result.all()
    ]

    # 4. Get top upstreams (with names)
    top_upstreams_query = (
        select(
            GatewayUpstream.name.label('upstream'),
            func.count(GatewayRequest.id).label('count')
        )
        .select_from(GatewayRequest)
        .join(GatewayUpstream, GatewayRequest.upstream_id == GatewayUpstream.id, isouter=True)
        .where(and_(base_filter, GatewayRequest.upstream_id.isnot(None)))
        .group_by(GatewayUpstream.name)
        .order_by(func.count(GatewayRequest.id).desc())
        .limit(10)
    )
    top_upstreams_result = await db.execute(top_upstreams_query)
    top_upstreams = [
        UpstreamCount(upstream=row.upstream or "Unknown", count=row.count)
        for row in top_upstreams_result.all()
    ]

    # 5. Get requests by hour
    # Use date_trunc for PostgreSQL - need to use literal_column for proper grouping
    hour_trunc = func.date_trunc('hour', GatewayRequest.created_at)
    requests_by_hour_query = (
        select(
            hour_trunc.label('hour'),
            func.count(GatewayRequest.id).label('count')
        )
        .where(base_filter)
        .group_by(hour_trunc)
        .order_by(hour_trunc)
    )
    requests_by_hour_result = await db.execute(requests_by_hour_query)
    requests_by_hour = [
        HourlyCount(
            hour=row.hour.isoformat() if row.hour else "",
            count=row.count
        )
        for row in requests_by_hour_result.all()
    ]

    return GatewayOverviewResponse(
        total_requests=total_requests,
        total_errors=total_errors,
        error_rate=round(error_rate, 2),
        avg_latency_ms=round(avg_latency_ms, 2),
        p95_latency_ms=round(p95_latency_ms, 2),
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost_usd, 6),
        top_models=top_models,
        top_upstreams=top_upstreams,
        requests_by_hour=requests_by_hour
    )
