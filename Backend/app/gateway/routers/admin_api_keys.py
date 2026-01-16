"""
Gateway Control Plane - API Keys API.

This module provides CRUD operations for managing gateway API keys.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_tenant_id, get_current_user
from app.core.session import SessionData
from app.models.gateway import GatewayAPIKey, LogPayloadMode
from app.gateway.middleware.auth import APIKeyGenerator


router = APIRouter(prefix="/api/gateway/api-keys", tags=["gateway-admin"])


# =============================================================================
# Schemas
# =============================================================================

class APIKeyCreate(BaseModel):
    """Schema for creating an API key."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    allowed_models: List[str] = Field(default_factory=list)
    allowed_endpoints: List[str] = Field(default_factory=list)
    rate_limit: Dict[str, Any] = Field(default_factory=dict)
    quota: Dict[str, Any] = Field(default_factory=dict)
    log_payload_mode: LogPayloadMode = LogPayloadMode.METADATA_ONLY
    expires_at: Optional[datetime] = None
    enabled: bool = True


class APIKeyUpdate(BaseModel):
    """Schema for updating an API key."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    allowed_models: Optional[List[str]] = None
    allowed_endpoints: Optional[List[str]] = None
    rate_limit: Optional[Dict[str, Any]] = None
    quota: Optional[Dict[str, Any]] = None
    log_payload_mode: Optional[LogPayloadMode] = None
    expires_at: Optional[datetime] = None
    enabled: Optional[bool] = None


class APIKeyResponse(BaseModel):
    """Schema for API key response (without full key)."""

    id: UUID
    name: str
    description: Optional[str]
    key_prefix: str
    allowed_models: List[str]
    allowed_endpoints: List[str]
    rate_limit: Dict[str, Any]
    quota: Dict[str, Any]
    log_payload_mode: str
    expires_at: Optional[datetime]
    enabled: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreateResponse(BaseModel):
    """Schema for API key creation response (includes full key)."""

    id: UUID
    name: str
    key: str  # Full key, shown only once
    key_prefix: str
    created_at: datetime


class APIKeyListResponse(BaseModel):
    """Schema for API key list response."""

    items: List[APIKeyResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    enabled: Optional[bool] = None,
    search: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """List all API keys for the current tenant."""

    stmt = select(GatewayAPIKey).where(GatewayAPIKey.tenant_id == tenant_id)

    if enabled is not None:
        stmt = stmt.where(GatewayAPIKey.enabled == enabled)
    if search:
        stmt = stmt.where(GatewayAPIKey.name.ilike(f"%{search}%"))

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
    stmt = stmt.order_by(GatewayAPIKey.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    keys = result.scalars().all()

    items = [
        APIKeyResponse(
            id=k.id,
            name=k.name,
            description=k.description,
            key_prefix=k.key_prefix,
            allowed_models=k.allowed_models or [],
            allowed_endpoints=k.allowed_endpoints or [],
            rate_limit=k.rate_limit or {},
            quota=k.quota or {},
            log_payload_mode=k.log_payload_mode.value if k.log_payload_mode else "metadata_only",
            expires_at=k.expires_at,
            enabled=k.enabled,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
            updated_at=k.updated_at
        )
        for k in keys
    ]

    return APIKeyListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=APIKeyCreateResponse, status_code=201)
async def create_api_key(
    data: APIKeyCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: SessionData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new API key.

    IMPORTANT: The full key is only returned once in this response.
    Store it securely as it cannot be retrieved again.
    """
    user_id = current_user.user_id

    # Check for duplicate name
    existing = await db.execute(
        select(GatewayAPIKey).where(
            GatewayAPIKey.tenant_id == tenant_id,
            GatewayAPIKey.name == data.name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="API key with this name already exists")

    # Generate key
    full_key, prefix, key_hash = APIKeyGenerator.generate()

    # Create API key record
    api_key = GatewayAPIKey(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        key_prefix=prefix,
        key_hash=key_hash,
        allowed_models=data.allowed_models,
        allowed_endpoints=data.allowed_endpoints,
        rate_limit=data.rate_limit,
        quota=data.quota,
        log_payload_mode=data.log_payload_mode,
        expires_at=data.expires_at,
        enabled=data.enabled,
        user_id=user_id,
        created_by=user_id
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=full_key,
        key_prefix=prefix,
        created_at=api_key.created_at
    )


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """Get an API key by ID."""

    stmt = select(GatewayAPIKey).where(
        GatewayAPIKey.id == key_id,
        GatewayAPIKey.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        description=api_key.description,
        key_prefix=api_key.key_prefix,
        allowed_models=api_key.allowed_models or [],
        allowed_endpoints=api_key.allowed_endpoints or [],
        rate_limit=api_key.rate_limit or {},
        quota=api_key.quota or {},
        log_payload_mode=api_key.log_payload_mode.value if api_key.log_payload_mode else "metadata_only",
        expires_at=api_key.expires_at,
        enabled=api_key.enabled,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at
    )


@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: UUID,
    data: APIKeyUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """Update an API key."""

    stmt = select(GatewayAPIKey).where(
        GatewayAPIKey.id == key_id,
        GatewayAPIKey.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(api_key, key, value)

    await db.commit()
    await db.refresh(api_key)

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        description=api_key.description,
        key_prefix=api_key.key_prefix,
        allowed_models=api_key.allowed_models or [],
        allowed_endpoints=api_key.allowed_endpoints or [],
        rate_limit=api_key.rate_limit or {},
        quota=api_key.quota or {},
        log_payload_mode=api_key.log_payload_mode.value if api_key.log_payload_mode else "metadata_only",
        expires_at=api_key.expires_at,
        enabled=api_key.enabled,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at
    )


@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """Delete an API key."""

    stmt = select(GatewayAPIKey).where(
        GatewayAPIKey.id == key_id,
        GatewayAPIKey.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(api_key)
    await db.commit()

    return None


@router.post("/{key_id}/regenerate", response_model=APIKeyCreateResponse)
async def regenerate_api_key(
    key_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Regenerate an API key.

    This creates a new key value while preserving the key's settings.
    The old key will immediately stop working.

    IMPORTANT: The full key is only returned once in this response.
    """

    stmt = select(GatewayAPIKey).where(
        GatewayAPIKey.id == key_id,
        GatewayAPIKey.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Generate new key
    full_key, prefix, key_hash = APIKeyGenerator.generate()

    # Update key
    api_key.key_prefix = prefix
    api_key.key_hash = key_hash
    api_key.last_used_at = None  # Reset usage tracking

    await db.commit()
    await db.refresh(api_key)

    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=full_key,
        key_prefix=prefix,
        created_at=api_key.created_at
    )
