"""
Gateway Control Plane - Upstreams API.

This module provides CRUD operations for managing upstream providers.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_tenant_id
from app.core.session import SessionData
from app.core.dependencies import get_current_user
from app.models.gateway import (
    GatewayUpstream,
    GatewaySecret,
    UpstreamType,
    AuthType,
)
from app.gateway.services.secret_manager import SecretManager, SecretManagerError


router = APIRouter(prefix="/api/gateway/upstreams", tags=["gateway-admin"])


# =============================================================================
# Schemas
# =============================================================================

class UpstreamCreate(BaseModel):
    """Schema for creating an upstream."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    type: UpstreamType
    base_url: str = Field(..., min_length=1, max_length=2000)
    auth_type: AuthType = AuthType.BEARER
    credentials: Optional[str] = Field(None, description="Plaintext credential (will be encrypted)")
    allow_hosts: List[str] = Field(default_factory=list)
    allow_cidrs: List[str] = Field(default_factory=list)
    supported_capabilities: List[str] = Field(default_factory=list)
    model_mapping: Dict[str, str] = Field(default_factory=dict)
    healthcheck: Dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=120000, ge=1000, le=600000)
    max_retries: int = Field(default=2, ge=0, le=10)
    circuit_breaker: Dict[str, Any] = Field(default_factory=dict)
    deployment_id: Optional[UUID] = None
    enabled: bool = True


class UpstreamUpdate(BaseModel):
    """Schema for updating an upstream."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    base_url: Optional[str] = None
    auth_type: Optional[AuthType] = None
    credentials: Optional[str] = None
    allow_hosts: Optional[List[str]] = None
    allow_cidrs: Optional[List[str]] = None
    supported_capabilities: Optional[List[str]] = None
    model_mapping: Optional[Dict[str, str]] = None
    healthcheck: Optional[Dict[str, Any]] = None
    timeout_ms: Optional[int] = None
    max_retries: Optional[int] = None
    circuit_breaker: Optional[Dict[str, Any]] = None
    deployment_id: Optional[UUID] = None
    enabled: Optional[bool] = None


class UpstreamResponse(BaseModel):
    """Schema for upstream response."""

    id: UUID
    name: str
    description: Optional[str]
    type: str
    base_url: str
    auth_type: str
    has_credentials: bool
    allow_hosts: List[str]
    allow_cidrs: List[str]
    supported_capabilities: List[str]
    model_mapping: Dict[str, str]
    healthcheck: Dict[str, Any]
    timeout_ms: int
    max_retries: int
    circuit_breaker: Dict[str, Any]
    health_status: str
    last_health_check_at: Optional[datetime]
    health_check_error: Optional[str]
    deployment_id: Optional[UUID]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpstreamListResponse(BaseModel):
    """Schema for upstream list response."""

    items: List[UpstreamResponse]
    total: int
    page: int
    page_size: int


class TestUpstreamRequest(BaseModel):
    """Schema for testing upstream connectivity."""

    upstream_id: UUID


class TestUpstreamResponse(BaseModel):
    """Schema for upstream test result."""

    success: bool
    latency_ms: Optional[int]
    error: Optional[str]
    capabilities_detected: List[str] = Field(default_factory=list)


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=UpstreamListResponse)
async def list_upstreams(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: Optional[UpstreamType] = None,
    enabled: Optional[bool] = None,
    search: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """List all upstreams for the current tenant."""

    # Build query
    stmt = select(GatewayUpstream).where(GatewayUpstream.tenant_id == tenant_id)

    if type:
        stmt = stmt.where(GatewayUpstream.type == type)
    if enabled is not None:
        stmt = stmt.where(GatewayUpstream.enabled == enabled)
    if search:
        stmt = stmt.where(GatewayUpstream.name.ilike(f"%{search}%"))

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
    stmt = stmt.order_by(GatewayUpstream.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    upstreams = result.scalars().all()

    items = [
        UpstreamResponse(
            id=u.id,
            name=u.name,
            description=u.description,
            type=u.type.value,
            base_url=u.base_url,
            auth_type=u.auth_type.value if u.auth_type else "bearer",
            has_credentials=u.credentials_secret_id is not None,
            allow_hosts=u.allow_hosts or [],
            allow_cidrs=u.allow_cidrs or [],
            supported_capabilities=u.supported_capabilities or [],
            model_mapping=u.model_mapping or {},
            healthcheck=u.healthcheck or {},
            timeout_ms=u.timeout_ms or 120000,
            max_retries=u.max_retries or 2,
            circuit_breaker=u.circuit_breaker or {},
            health_status=u.health_status or "unknown",
            last_health_check_at=u.last_health_check_at,
            health_check_error=u.health_check_error,
            deployment_id=u.deployment_id,
            enabled=u.enabled,
            created_at=u.created_at,
            updated_at=u.updated_at
        )
        for u in upstreams
    ]

    return UpstreamListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=UpstreamResponse, status_code=201)
async def create_upstream(
    data: UpstreamCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: SessionData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new upstream."""
    user_id = current_user.user_id

    # Check for duplicate name
    existing = await db.execute(
        select(GatewayUpstream).where(
            GatewayUpstream.tenant_id == tenant_id,
            GatewayUpstream.name == data.name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Upstream with this name already exists")

    # Create secret if credentials provided
    credentials_secret_id = None
    if data.credentials:
        try:
            secret_manager = SecretManager()
            ciphertext = secret_manager.encrypt(data.credentials)

            secret = GatewaySecret(
                tenant_id=tenant_id,
                name=f"upstream_{data.name}_credentials",
                description=f"Credentials for upstream {data.name}",
                ciphertext=ciphertext,
                created_by=user_id
            )
            db.add(secret)
            await db.flush()
            credentials_secret_id = secret.id
        except SecretManagerError as e:
            raise HTTPException(status_code=500, detail=f"Failed to encrypt credentials: {e}")

    # Create upstream
    upstream = GatewayUpstream(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        type=data.type,
        base_url=data.base_url,
        auth_type=data.auth_type,
        credentials_secret_id=credentials_secret_id,
        allow_hosts=data.allow_hosts,
        allow_cidrs=data.allow_cidrs,
        supported_capabilities=data.supported_capabilities,
        model_mapping=data.model_mapping,
        healthcheck=data.healthcheck,
        timeout_ms=data.timeout_ms,
        max_retries=data.max_retries,
        circuit_breaker=data.circuit_breaker,
        deployment_id=data.deployment_id,
        enabled=data.enabled,
        created_by=user_id
    )
    db.add(upstream)
    await db.commit()
    await db.refresh(upstream)

    return UpstreamResponse(
        id=upstream.id,
        name=upstream.name,
        description=upstream.description,
        type=upstream.type.value,
        base_url=upstream.base_url,
        auth_type=upstream.auth_type.value if upstream.auth_type else "bearer",
        has_credentials=credentials_secret_id is not None,
        allow_hosts=upstream.allow_hosts or [],
        allow_cidrs=upstream.allow_cidrs or [],
        supported_capabilities=upstream.supported_capabilities or [],
        model_mapping=upstream.model_mapping or {},
        healthcheck=upstream.healthcheck or {},
        timeout_ms=upstream.timeout_ms or 120000,
        max_retries=upstream.max_retries or 2,
        circuit_breaker=upstream.circuit_breaker or {},
        health_status=upstream.health_status or "unknown",
        last_health_check_at=upstream.last_health_check_at,
        health_check_error=upstream.health_check_error,
        deployment_id=upstream.deployment_id,
        enabled=upstream.enabled,
        created_at=upstream.created_at,
        updated_at=upstream.updated_at
    )


@router.get("/{upstream_id}", response_model=UpstreamResponse)
async def get_upstream(
    upstream_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """Get an upstream by ID."""

    stmt = select(GatewayUpstream).where(
        GatewayUpstream.id == upstream_id,
        GatewayUpstream.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    upstream = result.scalar_one_or_none()

    if not upstream:
        raise HTTPException(status_code=404, detail="Upstream not found")

    return UpstreamResponse(
        id=upstream.id,
        name=upstream.name,
        description=upstream.description,
        type=upstream.type.value,
        base_url=upstream.base_url,
        auth_type=upstream.auth_type.value if upstream.auth_type else "bearer",
        has_credentials=upstream.credentials_secret_id is not None,
        allow_hosts=upstream.allow_hosts or [],
        allow_cidrs=upstream.allow_cidrs or [],
        supported_capabilities=upstream.supported_capabilities or [],
        model_mapping=upstream.model_mapping or {},
        healthcheck=upstream.healthcheck or {},
        timeout_ms=upstream.timeout_ms or 120000,
        max_retries=upstream.max_retries or 2,
        circuit_breaker=upstream.circuit_breaker or {},
        health_status=upstream.health_status or "unknown",
        last_health_check_at=upstream.last_health_check_at,
        health_check_error=upstream.health_check_error,
        deployment_id=upstream.deployment_id,
        enabled=upstream.enabled,
        created_at=upstream.created_at,
        updated_at=upstream.updated_at
    )


@router.put("/{upstream_id}", response_model=UpstreamResponse)
async def update_upstream(
    upstream_id: UUID,
    data: UpstreamUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: SessionData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an upstream."""

    stmt = select(GatewayUpstream).where(
        GatewayUpstream.id == upstream_id,
        GatewayUpstream.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    upstream = result.scalar_one_or_none()

    if not upstream:
        raise HTTPException(status_code=404, detail="Upstream not found")

    # Update fields
    update_data = data.model_dump(exclude_unset=True, exclude={"credentials"})
    for key, value in update_data.items():
        setattr(upstream, key, value)

    # Handle credential update
    if data.credentials is not None:
        try:
            secret_manager = SecretManager()
            ciphertext = secret_manager.encrypt(data.credentials)

            if upstream.credentials_secret_id:
                # Update existing secret
                secret_stmt = select(GatewaySecret).where(
                    GatewaySecret.id == upstream.credentials_secret_id
                )
                secret_result = await db.execute(secret_stmt)
                secret = secret_result.scalar_one_or_none()
                if secret:
                    secret.ciphertext = ciphertext
            else:
                # Create new secret
                secret = GatewaySecret(
                    tenant_id=tenant_id,
                    name=f"upstream_{upstream.name}_credentials",
                    description=f"Credentials for upstream {upstream.name}",
                    ciphertext=ciphertext,
                    created_by=current_user.user_id
                )
                db.add(secret)
                await db.flush()
                upstream.credentials_secret_id = secret.id
        except SecretManagerError as e:
            raise HTTPException(status_code=500, detail=f"Failed to encrypt credentials: {e}")

    await db.commit()
    await db.refresh(upstream)

    return UpstreamResponse(
        id=upstream.id,
        name=upstream.name,
        description=upstream.description,
        type=upstream.type.value,
        base_url=upstream.base_url,
        auth_type=upstream.auth_type.value if upstream.auth_type else "bearer",
        has_credentials=upstream.credentials_secret_id is not None,
        allow_hosts=upstream.allow_hosts or [],
        allow_cidrs=upstream.allow_cidrs or [],
        supported_capabilities=upstream.supported_capabilities or [],
        model_mapping=upstream.model_mapping or {},
        healthcheck=upstream.healthcheck or {},
        timeout_ms=upstream.timeout_ms or 120000,
        max_retries=upstream.max_retries or 2,
        circuit_breaker=upstream.circuit_breaker or {},
        health_status=upstream.health_status or "unknown",
        last_health_check_at=upstream.last_health_check_at,
        health_check_error=upstream.health_check_error,
        deployment_id=upstream.deployment_id,
        enabled=upstream.enabled,
        created_at=upstream.created_at,
        updated_at=upstream.updated_at
    )


@router.delete("/{upstream_id}", status_code=204)
async def delete_upstream(
    upstream_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """Delete an upstream."""

    stmt = select(GatewayUpstream).where(
        GatewayUpstream.id == upstream_id,
        GatewayUpstream.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    upstream = result.scalar_one_or_none()

    if not upstream:
        raise HTTPException(status_code=404, detail="Upstream not found")

    # Delete associated secret
    if upstream.credentials_secret_id:
        secret_stmt = select(GatewaySecret).where(
            GatewaySecret.id == upstream.credentials_secret_id
        )
        secret_result = await db.execute(secret_stmt)
        secret = secret_result.scalar_one_or_none()
        if secret:
            await db.delete(secret)

    await db.delete(upstream)
    await db.commit()

    return None


@router.post("/{upstream_id}/test", response_model=TestUpstreamResponse)
async def test_upstream(
    upstream_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """Test upstream connectivity and capabilities."""
    import time
    import httpx

    stmt = select(GatewayUpstream).where(
        GatewayUpstream.id == upstream_id,
        GatewayUpstream.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    upstream = result.scalar_one_or_none()

    if not upstream:
        raise HTTPException(status_code=404, detail="Upstream not found")

    # Get credentials if available
    credentials = None
    if upstream.credentials_secret_id:
        secret_stmt = select(GatewaySecret).where(
            GatewaySecret.id == upstream.credentials_secret_id
        )
        secret_result = await db.execute(secret_stmt)
        secret = secret_result.scalar_one_or_none()
        if secret:
            try:
                secret_manager = SecretManager()
                credentials = secret_manager.decrypt(secret.ciphertext)
            except SecretManagerError:
                pass

    # Test connectivity
    start_time = time.time()
    capabilities_detected = []

    try:
        # Build health check URL
        healthcheck = upstream.healthcheck or {}
        health_path = healthcheck.get("path", "/health")
        health_url = f"{upstream.base_url.rstrip('/')}{health_path}"

        headers = {}
        if upstream.auth_type == AuthType.BEARER and credentials:
            headers["Authorization"] = f"Bearer {credentials}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(health_url, headers=headers)
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code < 400:
                # Try to detect capabilities by calling /v1/models
                try:
                    models_url = f"{upstream.base_url.rstrip('/')}/v1/models"
                    models_response = await client.get(models_url, headers=headers)
                    if models_response.status_code == 200:
                        capabilities_detected.append("chat_completions")
                        capabilities_detected.append("completions")
                except Exception:
                    pass

                # Update health status
                upstream.health_status = "healthy"
                upstream.last_health_check_at = datetime.utcnow()
                upstream.health_check_error = None
                await db.commit()

                return TestUpstreamResponse(
                    success=True,
                    latency_ms=latency_ms,
                    error=None,
                    capabilities_detected=capabilities_detected
                )
            else:
                upstream.health_status = "unhealthy"
                upstream.last_health_check_at = datetime.utcnow()
                upstream.health_check_error = f"HTTP {response.status_code}"
                await db.commit()

                return TestUpstreamResponse(
                    success=False,
                    latency_ms=latency_ms,
                    error=f"HTTP {response.status_code}",
                    capabilities_detected=[]
                )

    except httpx.TimeoutException:
        upstream.health_status = "unhealthy"
        upstream.last_health_check_at = datetime.utcnow()
        upstream.health_check_error = "Connection timeout"
        await db.commit()

        return TestUpstreamResponse(
            success=False,
            latency_ms=None,
            error="Connection timeout",
            capabilities_detected=[]
        )
    except Exception as e:
        upstream.health_status = "unhealthy"
        upstream.last_health_check_at = datetime.utcnow()
        upstream.health_check_error = str(e)
        await db.commit()

        return TestUpstreamResponse(
            success=False,
            latency_ms=None,
            error=str(e),
            capabilities_detected=[]
        )
