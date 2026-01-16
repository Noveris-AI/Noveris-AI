"""
Chat Admin API Endpoints.

This module provides admin endpoints for the chat module:
- Model profile management
- Conversation management
- Message handling (including streaming)
- File upload
- Tool configuration

All endpoints require authentication (session + cookie).
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import RequirePermission
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUserDep, TenantIdDep
from app.models.chat import (
    ChatModelProfile,
    ChatConversation,
    ChatMessage,
    ChatAttachment,
    ChatPublicApp,
    ChatMCPServer,
    MessageRole,
)
from app.models.gateway import GatewaySecret
from app.gateway.services.secret_manager import SecretManager
from app.chat.services.conversations import (
    ConversationService,
    ConversationCreate,
    MessageCreate,
    create_conversation_service,
)
from app.chat.services.uploads import UploadService, create_upload_service
from app.chat.services.openai_client import ModelProfileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat-admin"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class ModelProfileCreate(BaseModel):
    """Create model profile request."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    base_url: str = Field(..., max_length=2000)
    api_key: Optional[str] = None
    default_model: str = Field(..., max_length=255)
    available_models: List[str] = []
    capabilities: List[str] = []
    headers: Dict[str, str] = {}
    default_params: Dict[str, Any] = {}
    timeout_ms: int = 120000
    is_default: bool = False


class ModelProfileUpdate(BaseModel):
    """Update model profile request."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    base_url: Optional[str] = Field(None, max_length=2000)
    api_key: Optional[str] = None
    default_model: Optional[str] = Field(None, max_length=255)
    available_models: Optional[List[str]] = None
    capabilities: Optional[List[str]] = None
    headers: Optional[Dict[str, str]] = None
    default_params: Optional[Dict[str, Any]] = None
    timeout_ms: Optional[int] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class ModelProfileResponse(BaseModel):
    """Model profile response."""
    id: str
    name: str
    description: Optional[str]
    base_url: str
    has_api_key: bool
    default_model: str
    available_models: List[str]
    capabilities: List[str]
    headers: Dict[str, str]
    default_params: Dict[str, Any]
    timeout_ms: int
    enabled: bool
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationCreateRequest(BaseModel):
    """Create conversation request."""
    title: Optional[str] = Field(None, max_length=500)
    model_profile_id: Optional[str] = None
    model: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class ConversationUpdateRequest(BaseModel):
    """Update conversation request."""
    title: Optional[str] = Field(None, max_length=500)
    pinned: Optional[bool] = None
    model_profile_id: Optional[str] = None
    model: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    """Conversation response."""
    id: str
    title: str
    pinned: bool
    model_profile_id: Optional[str]
    model: Optional[str]
    settings: Dict[str, Any]
    message_count: int
    last_message_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Message response."""
    id: str
    role: str
    content: Any
    model: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    """Send message request."""
    content: str
    attachment_ids: Optional[List[str]] = None


class AttachmentResponse(BaseModel):
    """Attachment response."""
    id: str
    file_name: str
    mime_type: str
    size_bytes: int
    extraction_status: str
    embedding_status: str
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Model Profile Endpoints
# =============================================================================

@router.post(
    "/model-profiles",
    response_model=ModelProfileResponse,
    dependencies=[Depends(RequirePermission("chat.model_profile.create"))],
)
async def create_model_profile(
    request: ModelProfileCreate,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Create a new model profile."""
    # Handle API key encryption
    api_key_secret_id = None
    if request.api_key:
        secret_manager = SecretManager()
        ciphertext = secret_manager.encrypt(request.api_key)

        secret = GatewaySecret(
            tenant_id=tenant_id,
            name=f"chat-profile-{request.name}",
            ciphertext=ciphertext,
            created_by=user.id
        )
        db.add(secret)
        await db.flush()
        api_key_secret_id = secret.id

    # If setting as default, unset other defaults
    if request.is_default:
        await db.execute(
            update(ChatModelProfile)
            .where(ChatModelProfile.tenant_id == tenant_id)
            .values(is_default=False)
        )

    profile = ChatModelProfile(
        tenant_id=tenant_id,
        name=request.name,
        description=request.description,
        base_url=request.base_url,
        api_key_secret_id=api_key_secret_id,
        default_model=request.default_model,
        available_models=request.available_models,
        capabilities=request.capabilities,
        headers=request.headers,
        default_params=request.default_params,
        timeout_ms=request.timeout_ms,
        is_default=request.is_default,
        created_by=user.id
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return ModelProfileResponse(
        id=str(profile.id),
        name=profile.name,
        description=profile.description,
        base_url=profile.base_url,
        has_api_key=api_key_secret_id is not None,
        default_model=profile.default_model,
        available_models=profile.available_models or [],
        capabilities=profile.capabilities or [],
        headers=profile.headers or {},
        default_params=profile.default_params or {},
        timeout_ms=profile.timeout_ms,
        enabled=profile.enabled,
        is_default=profile.is_default,
        created_at=profile.created_at
    )


@router.get(
    "/model-profiles",
    response_model=List[ModelProfileResponse],
    dependencies=[Depends(RequirePermission("chat.model_profile.view"))],
)
async def list_model_profiles(
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    capability: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all model profiles."""
    stmt = select(ChatModelProfile).where(
        ChatModelProfile.tenant_id == tenant_id,
        ChatModelProfile.enabled == True
    )

    if capability:
        stmt = stmt.where(ChatModelProfile.capabilities.contains([capability]))

    result = await db.execute(stmt)
    profiles = result.scalars().all()

    return [
        ModelProfileResponse(
            id=str(p.id),
            name=p.name,
            description=p.description,
            base_url=p.base_url,
            has_api_key=p.api_key_secret_id is not None,
            default_model=p.default_model,
            available_models=p.available_models or [],
            capabilities=p.capabilities or [],
            headers=p.headers or {},
            default_params=p.default_params or {},
            timeout_ms=p.timeout_ms,
            enabled=p.enabled,
            is_default=p.is_default,
            created_at=p.created_at
        )
        for p in profiles
    ]


@router.get(
    "/model-profiles/{profile_id}",
    response_model=ModelProfileResponse,
    dependencies=[Depends(RequirePermission("chat.model_profile.view"))],
)
async def get_model_profile(
    profile_id: str,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific model profile."""
    stmt = select(ChatModelProfile).where(
        ChatModelProfile.id == UUID(profile_id),
        ChatModelProfile.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Model profile not found")

    return ModelProfileResponse(
        id=str(profile.id),
        name=profile.name,
        description=profile.description,
        base_url=profile.base_url,
        has_api_key=profile.api_key_secret_id is not None,
        default_model=profile.default_model,
        available_models=profile.available_models or [],
        capabilities=profile.capabilities or [],
        headers=profile.headers or {},
        default_params=profile.default_params or {},
        timeout_ms=profile.timeout_ms,
        enabled=profile.enabled,
        is_default=profile.is_default,
        created_at=profile.created_at
    )


@router.patch(
    "/model-profiles/{profile_id}",
    response_model=ModelProfileResponse,
    dependencies=[Depends(RequirePermission("chat.model_profile.update"))],
)
async def update_model_profile(
    profile_id: str,
    request: ModelProfileUpdate,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Update a model profile."""
    stmt = select(ChatModelProfile).where(
        ChatModelProfile.id == UUID(profile_id),
        ChatModelProfile.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Model profile not found")

    # Handle API key update
    if request.api_key is not None:
        secret_manager = SecretManager()
        if request.api_key:
            ciphertext = secret_manager.encrypt(request.api_key)

            if profile.api_key_secret_id:
                # Update existing secret
                await db.execute(
                    update(GatewaySecret)
                    .where(GatewaySecret.id == profile.api_key_secret_id)
                    .values(ciphertext=ciphertext)
                )
            else:
                # Create new secret
                secret = GatewaySecret(
                    tenant_id=tenant_id,
                    name=f"chat-profile-{profile.name}",
                    ciphertext=ciphertext,
                    created_by=user.id
                )
                db.add(secret)
                await db.flush()
                profile.api_key_secret_id = secret.id
        else:
            profile.api_key_secret_id = None

    # Update other fields
    update_data = request.model_dump(exclude_unset=True, exclude={"api_key"})

    # Handle is_default
    if request.is_default:
        await db.execute(
            update(ChatModelProfile)
            .where(
                ChatModelProfile.tenant_id == tenant_id,
                ChatModelProfile.id != UUID(profile_id)
            )
            .values(is_default=False)
        )

    for key, value in update_data.items():
        setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)

    return ModelProfileResponse(
        id=str(profile.id),
        name=profile.name,
        description=profile.description,
        base_url=profile.base_url,
        has_api_key=profile.api_key_secret_id is not None,
        default_model=profile.default_model,
        available_models=profile.available_models or [],
        capabilities=profile.capabilities or [],
        headers=profile.headers or {},
        default_params=profile.default_params or {},
        timeout_ms=profile.timeout_ms,
        enabled=profile.enabled,
        is_default=profile.is_default,
        created_at=profile.created_at
    )


@router.delete(
    "/model-profiles/{profile_id}",
    dependencies=[Depends(RequirePermission("chat.model_profile.delete"))],
)
async def delete_model_profile(
    profile_id: str,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Delete a model profile."""
    stmt = select(ChatModelProfile).where(
        ChatModelProfile.id == UUID(profile_id),
        ChatModelProfile.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Model profile not found")

    # Soft delete by disabling
    profile.enabled = False
    await db.commit()

    return {"success": True}


# =============================================================================
# Conversation Endpoints
# =============================================================================

@router.post(
    "/conversations",
    response_model=ConversationResponse,
    dependencies=[Depends(RequirePermission("chat.conversation.create"))],
)
async def create_conversation(
    request: ConversationCreateRequest,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation."""
    service = create_conversation_service(db, tenant_id, user.id)

    params = ConversationCreate(
        title=request.title,
        model_profile_id=UUID(request.model_profile_id) if request.model_profile_id else None,
        model=request.model,
        settings=request.settings
    )

    conversation = await service.create_conversation(params)

    return ConversationResponse(
        id=str(conversation.id),
        title=conversation.title,
        pinned=conversation.pinned,
        model_profile_id=str(conversation.active_model_profile_id) if conversation.active_model_profile_id else None,
        model=conversation.active_model,
        settings=conversation.settings or {},
        message_count=conversation.message_count,
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )


@router.get(
    "/conversations",
    response_model=Dict[str, Any],
    dependencies=[Depends(RequirePermission("chat.conversation.view"))],
)
async def list_conversations(
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List conversations for the current user."""
    service = create_conversation_service(db, tenant_id, user.id)

    conversations, total = await service.list_conversations(limit, offset, search)

    return {
        "data": [
            ConversationResponse(
                id=str(c.id),
                title=c.title,
                pinned=c.pinned,
                model_profile_id=str(c.active_model_profile_id) if c.active_model_profile_id else None,
                model=c.active_model,
                settings=c.settings or {},
                message_count=c.message_count,
                last_message_at=c.last_message_at,
                created_at=c.created_at,
                updated_at=c.updated_at
            )
            for c in conversations
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    dependencies=[Depends(RequirePermission("chat.conversation.view"))],
)
async def get_conversation(
    conversation_id: str,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific conversation."""
    service = create_conversation_service(db, tenant_id, user.id)
    conversation = await service.get_conversation(UUID(conversation_id))

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(
        id=str(conversation.id),
        title=conversation.title,
        pinned=conversation.pinned,
        model_profile_id=str(conversation.active_model_profile_id) if conversation.active_model_profile_id else None,
        model=conversation.active_model,
        settings=conversation.settings or {},
        message_count=conversation.message_count,
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    dependencies=[Depends(RequirePermission("chat.conversation.update"))],
)
async def update_conversation(
    conversation_id: str,
    request: ConversationUpdateRequest,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Update a conversation."""
    service = create_conversation_service(db, tenant_id, user.id)

    conversation = await service.update_conversation(
        UUID(conversation_id),
        title=request.title,
        pinned=request.pinned,
        model_profile_id=UUID(request.model_profile_id) if request.model_profile_id else None,
        model=request.model,
        settings=request.settings
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(
        id=str(conversation.id),
        title=conversation.title,
        pinned=conversation.pinned,
        model_profile_id=str(conversation.active_model_profile_id) if conversation.active_model_profile_id else None,
        model=conversation.active_model,
        settings=conversation.settings or {},
        message_count=conversation.message_count,
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )


@router.delete(
    "/conversations/{conversation_id}",
    dependencies=[Depends(RequirePermission("chat.conversation.delete"))],
)
async def delete_conversation(
    conversation_id: str,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Delete a conversation."""
    service = create_conversation_service(db, tenant_id, user.id)
    success = await service.delete_conversation(UUID(conversation_id))

    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"success": True}


# =============================================================================
# Message Endpoints
# =============================================================================

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[MessageResponse],
    dependencies=[Depends(RequirePermission("chat.conversation.view"))],
)
async def get_messages(
    conversation_id: str,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    limit: int = Query(100, ge=1, le=500),
    before_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a conversation."""
    service = create_conversation_service(db, tenant_id, user.id)

    messages = await service.get_messages(
        UUID(conversation_id),
        limit=limit,
        before_id=UUID(before_id) if before_id else None
    )

    return [
        MessageResponse(
            id=str(m.id),
            role=m.role.value,
            content=m.content,
            model=m.model,
            prompt_tokens=m.prompt_tokens,
            completion_tokens=m.completion_tokens,
            created_at=m.created_at
        )
        for m in messages
    ]


@router.post(
    "/conversations/{conversation_id}/send",
    dependencies=[Depends(RequirePermission("chat.conversation.execute"))],
)
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message and get streaming response.

    Returns Server-Sent Events (SSE) stream.
    """
    service = create_conversation_service(db, tenant_id, user.id)

    attachment_ids = [UUID(aid) for aid in request.attachment_ids] if request.attachment_ids else None

    async def event_generator():
        async for event in service.send_message(
            UUID(conversation_id),
            request.content,
            attachment_ids
        ):
            data = {
                "type": event.type,
                "data": event.data,
                "error": event.error
            }
            yield f"data: {json.dumps(data)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post(
    "/conversations/{conversation_id}/regenerate/{message_id}",
    dependencies=[Depends(RequirePermission("chat.conversation.execute"))],
)
async def regenerate_message(
    conversation_id: str,
    message_id: str,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Regenerate a response from a specific message."""
    service = create_conversation_service(db, tenant_id, user.id)

    async def event_generator():
        async for event in service.regenerate_message(
            UUID(conversation_id),
            UUID(message_id)
        ):
            data = {
                "type": event.type,
                "data": event.data,
                "error": event.error
            }
            yield f"data: {json.dumps(data)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# =============================================================================
# File Upload Endpoints
# =============================================================================

@router.post(
    "/conversations/{conversation_id}/upload",
    response_model=AttachmentResponse,
    dependencies=[Depends(RequirePermission("chat.conversation.upload"))],
)
async def upload_file(
    conversation_id: str,
    file: UploadFile = File(...),
    usage_mode: str = Form("retrieval"),
    user: CurrentUserDep = None,
    tenant_id: TenantIdDep = None,
    db: AsyncSession = Depends(get_db)
):
    """Upload a file to a conversation."""
    # Read file content
    content = await file.read()

    upload_service = create_upload_service(db, tenant_id)

    try:
        attachment = await upload_service.upload_file(
            conversation_id=UUID(conversation_id),
            file_name=file.filename or "unnamed",
            content=content,
            mime_type=file.content_type or "application/octet-stream",
            user_id=user.id,
            usage_mode=usage_mode
        )

        # Start document processing in background
        # In production, this would be a Celery task
        asyncio.create_task(
            upload_service.process_document(attachment.id)
        )

        return AttachmentResponse(
            id=str(attachment.id),
            file_name=attachment.file_name,
            mime_type=attachment.mime_type,
            size_bytes=attachment.size_bytes,
            extraction_status=attachment.extraction_status,
            embedding_status=attachment.embedding_status,
            chunk_count=attachment.chunk_count,
            created_at=attachment.created_at
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/conversations/{conversation_id}/attachments",
    response_model=List[AttachmentResponse],
    dependencies=[Depends(RequirePermission("chat.conversation.view"))],
)
async def list_attachments(
    conversation_id: str,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """List attachments for a conversation."""
    stmt = select(ChatAttachment).where(
        ChatAttachment.conversation_id == UUID(conversation_id)
    ).order_by(ChatAttachment.created_at.desc())

    result = await db.execute(stmt)
    attachments = result.scalars().all()

    return [
        AttachmentResponse(
            id=str(a.id),
            file_name=a.file_name,
            mime_type=a.mime_type,
            size_bytes=a.size_bytes,
            extraction_status=a.extraction_status,
            embedding_status=a.embedding_status,
            chunk_count=a.chunk_count,
            created_at=a.created_at
        )
        for a in attachments
    ]


@router.delete(
    "/attachments/{attachment_id}",
    dependencies=[Depends(RequirePermission("chat.conversation.delete"))],
)
async def delete_attachment(
    attachment_id: str,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Delete an attachment."""
    upload_service = create_upload_service(db, tenant_id)
    success = await upload_service.delete_file(UUID(attachment_id))

    if not success:
        raise HTTPException(status_code=404, detail="Attachment not found")

    return {"success": True}
