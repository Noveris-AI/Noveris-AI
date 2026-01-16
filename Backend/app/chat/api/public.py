"""
Chat Public API Endpoints.

This module provides public endpoints for the chat module:
- Public chat apps (shareable chat interfaces)
- OpenAI-compatible chat completions API

These endpoints use token-based authentication (not session).
"""

import asyncio
import hashlib
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import TenantIdDep, CurrentUserDep
from app.models.chat import (
    ChatModelProfile,
    ChatConversation,
    ChatMessage,
    ChatPublicApp,
    MessageRole,
)
from app.chat.services.conversations import (
    ConversationService,
    ConversationCreate,
    create_conversation_service,
)
from app.chat.services.uploads import create_upload_service
from app.chat.services.openai_client import (
    OpenAIClient,
    ChatCompletionRequest,
    ChatMessage as OpenAIChatMessage,
    ModelProfileService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["chat-public"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class PublicAppCreate(BaseModel):
    """Create public app request."""
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = Field(None, max_length=2000)
    welcome_message: Optional[str] = None
    allowed_model_profile_ids: List[str] = []
    default_model_profile_id: Optional[str] = None
    allow_upload: bool = False
    allow_web_search: bool = False
    allow_doc_search: bool = True
    allow_model_selection: bool = False
    system_prompt: Optional[str] = None
    model_params: Dict[str, Any] = {}
    rate_limit: Dict[str, int] = {}
    max_messages_per_conversation: int = 100
    expires_at: Optional[datetime] = None


class PublicAppUpdate(BaseModel):
    """Update public app request."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    welcome_message: Optional[str] = None
    allowed_model_profile_ids: Optional[List[str]] = None
    default_model_profile_id: Optional[str] = None
    allow_upload: Optional[bool] = None
    allow_web_search: Optional[bool] = None
    allow_doc_search: Optional[bool] = None
    allow_model_selection: Optional[bool] = None
    system_prompt: Optional[str] = None
    model_params: Optional[Dict[str, Any]] = None
    rate_limit: Optional[Dict[str, int]] = None
    max_messages_per_conversation: Optional[int] = None
    enabled: Optional[bool] = None
    expires_at: Optional[datetime] = None


class PublicAppResponse(BaseModel):
    """Public app response."""
    id: str
    slug: str
    name: str
    description: Optional[str]
    welcome_message: Optional[str]
    token_prefix: Optional[str]
    allowed_model_profile_ids: List[str]
    default_model_profile_id: Optional[str]
    allow_upload: bool
    allow_web_search: bool
    allow_doc_search: bool
    allow_model_selection: bool
    system_prompt: Optional[str]
    rate_limit: Dict[str, Any]
    max_messages_per_conversation: int
    enabled: bool
    expires_at: Optional[datetime]
    total_conversations: int
    total_messages: int
    created_at: datetime


class PublicAppConfigResponse(BaseModel):
    """Public app configuration (for frontend)."""
    name: str
    description: Optional[str]
    welcome_message: Optional[str]
    allow_upload: bool
    allow_web_search: bool
    allow_model_selection: bool
    models: List[Dict[str, Any]]
    default_model: Optional[str]
    branding: Dict[str, Any]


class PublicChatRequest(BaseModel):
    """OpenAI-compatible chat completion request."""
    model: str
    messages: List[Dict[str, Any]]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class PublicSendRequest(BaseModel):
    """Send message request for public app."""
    content: str
    conversation_id: Optional[str] = None


# =============================================================================
# Token Authentication
# =============================================================================

async def get_public_app_from_token(
    slug: str,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> ChatPublicApp:
    """Authenticate using public app token."""
    # Get token from header or query
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization[7:]
    elif token:
        auth_token = token

    if not auth_token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    # Hash the token and look up the app
    token_hash = hashlib.sha256(auth_token.encode()).hexdigest()

    stmt = select(ChatPublicApp).where(
        ChatPublicApp.slug == slug,
        ChatPublicApp.token_hash == token_hash,
        ChatPublicApp.enabled == True
    )
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Check expiration
    if app.expires_at and app.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expired")

    return app


# =============================================================================
# Admin Endpoints for Public Apps (require session auth)
# =============================================================================

@router.post("/apps", response_model=PublicAppResponse, tags=["chat-admin"])
async def create_public_app(
    request: PublicAppCreate,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Create a new public app."""
    # Check slug uniqueness
    stmt = select(ChatPublicApp).where(ChatPublicApp.slug == request.slug)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug already exists")

    # Generate token
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    token_prefix = token[:8]

    app = ChatPublicApp(
        tenant_id=tenant_id,
        slug=request.slug,
        name=request.name,
        description=request.description,
        welcome_message=request.welcome_message,
        token_hash=token_hash,
        token_prefix=token_prefix,
        allowed_model_profile_ids=[UUID(pid) for pid in request.allowed_model_profile_ids],
        default_model_profile_id=UUID(request.default_model_profile_id) if request.default_model_profile_id else None,
        allow_upload=request.allow_upload,
        allow_web_search=request.allow_web_search and settings.mcp.web_search_enabled,
        allow_doc_search=request.allow_doc_search,
        allow_model_selection=request.allow_model_selection,
        system_prompt=request.system_prompt,
        model_params=request.model_params,
        rate_limit=request.rate_limit,
        max_messages_per_conversation=request.max_messages_per_conversation,
        expires_at=request.expires_at,
        created_by=user.id
    )

    db.add(app)
    await db.commit()
    await db.refresh(app)

    # Return with the actual token (only shown once)
    response = PublicAppResponse(
        id=str(app.id),
        slug=app.slug,
        name=app.name,
        description=app.description,
        welcome_message=app.welcome_message,
        token_prefix=token_prefix,
        allowed_model_profile_ids=[str(pid) for pid in app.allowed_model_profile_ids or []],
        default_model_profile_id=str(app.default_model_profile_id) if app.default_model_profile_id else None,
        allow_upload=app.allow_upload,
        allow_web_search=app.allow_web_search,
        allow_doc_search=app.allow_doc_search,
        allow_model_selection=app.allow_model_selection,
        system_prompt=app.system_prompt,
        rate_limit=app.rate_limit or {},
        max_messages_per_conversation=app.max_messages_per_conversation,
        enabled=app.enabled,
        expires_at=app.expires_at,
        total_conversations=app.total_conversations,
        total_messages=app.total_messages,
        created_at=app.created_at
    )

    # Include the full token in metadata (only on create)
    return JSONResponse(content={
        **response.model_dump(mode="json"),
        "token": token  # Only returned on creation
    })


@router.get("/apps", response_model=List[PublicAppResponse], tags=["chat-admin"])
async def list_public_apps(
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """List all public apps for the tenant."""
    stmt = select(ChatPublicApp).where(
        ChatPublicApp.tenant_id == tenant_id
    ).order_by(ChatPublicApp.created_at.desc())

    result = await db.execute(stmt)
    apps = result.scalars().all()

    return [
        PublicAppResponse(
            id=str(app.id),
            slug=app.slug,
            name=app.name,
            description=app.description,
            welcome_message=app.welcome_message,
            token_prefix=app.token_prefix,
            allowed_model_profile_ids=[str(pid) for pid in app.allowed_model_profile_ids or []],
            default_model_profile_id=str(app.default_model_profile_id) if app.default_model_profile_id else None,
            allow_upload=app.allow_upload,
            allow_web_search=app.allow_web_search,
            allow_doc_search=app.allow_doc_search,
            allow_model_selection=app.allow_model_selection,
            system_prompt=app.system_prompt,
            rate_limit=app.rate_limit or {},
            max_messages_per_conversation=app.max_messages_per_conversation,
            enabled=app.enabled,
            expires_at=app.expires_at,
            total_conversations=app.total_conversations,
            total_messages=app.total_messages,
            created_at=app.created_at
        )
        for app in apps
    ]


@router.patch("/apps/{app_id}", response_model=PublicAppResponse, tags=["chat-admin"])
async def update_public_app(
    app_id: str,
    request: PublicAppUpdate,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Update a public app."""
    stmt = select(ChatPublicApp).where(
        ChatPublicApp.id == UUID(app_id),
        ChatPublicApp.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=404, detail="Public app not found")

    update_data = request.model_dump(exclude_unset=True)

    # Convert UUIDs
    if "allowed_model_profile_ids" in update_data and update_data["allowed_model_profile_ids"] is not None:
        update_data["allowed_model_profile_ids"] = [UUID(pid) for pid in update_data["allowed_model_profile_ids"]]
    if "default_model_profile_id" in update_data and update_data["default_model_profile_id"]:
        update_data["default_model_profile_id"] = UUID(update_data["default_model_profile_id"])

    # Enforce global web search setting
    if "allow_web_search" in update_data:
        update_data["allow_web_search"] = update_data["allow_web_search"] and settings.mcp.web_search_enabled

    for key, value in update_data.items():
        setattr(app, key, value)

    await db.commit()
    await db.refresh(app)

    return PublicAppResponse(
        id=str(app.id),
        slug=app.slug,
        name=app.name,
        description=app.description,
        welcome_message=app.welcome_message,
        token_prefix=app.token_prefix,
        allowed_model_profile_ids=[str(pid) for pid in app.allowed_model_profile_ids or []],
        default_model_profile_id=str(app.default_model_profile_id) if app.default_model_profile_id else None,
        allow_upload=app.allow_upload,
        allow_web_search=app.allow_web_search,
        allow_doc_search=app.allow_doc_search,
        allow_model_selection=app.allow_model_selection,
        system_prompt=app.system_prompt,
        rate_limit=app.rate_limit or {},
        max_messages_per_conversation=app.max_messages_per_conversation,
        enabled=app.enabled,
        expires_at=app.expires_at,
        total_conversations=app.total_conversations,
        total_messages=app.total_messages,
        created_at=app.created_at
    )


@router.delete("/apps/{app_id}", tags=["chat-admin"])
async def delete_public_app(
    app_id: str,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Delete a public app."""
    stmt = select(ChatPublicApp).where(
        ChatPublicApp.id == UUID(app_id),
        ChatPublicApp.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=404, detail="Public app not found")

    # Soft delete
    app.enabled = False
    await db.commit()

    return {"success": True}


@router.post("/apps/{app_id}/regenerate-token", tags=["chat-admin"])
async def regenerate_app_token(
    app_id: str,
    user: CurrentUserDep,
    tenant_id: TenantIdDep,
    db: AsyncSession = Depends(get_db)
):
    """Regenerate the access token for a public app."""
    stmt = select(ChatPublicApp).where(
        ChatPublicApp.id == UUID(app_id),
        ChatPublicApp.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=404, detail="Public app not found")

    # Generate new token
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    token_prefix = token[:8]

    app.token_hash = token_hash
    app.token_prefix = token_prefix

    await db.commit()

    return {"token": token, "token_prefix": token_prefix}


# =============================================================================
# Public Endpoints (token auth)
# =============================================================================

@router.get("/apps/{slug}/config", response_model=PublicAppConfigResponse)
async def get_app_config(
    slug: str,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get public app configuration for the frontend."""
    app = await get_public_app_from_token(slug, authorization, token, db)

    # Get available models
    models = []
    if app.allow_model_selection and app.allowed_model_profile_ids:
        stmt = select(ChatModelProfile).where(
            ChatModelProfile.id.in_(app.allowed_model_profile_ids),
            ChatModelProfile.enabled == True
        )
        result = await db.execute(stmt)
        profiles = result.scalars().all()

        for p in profiles:
            models.append({
                "id": str(p.id),
                "name": p.name,
                "default_model": p.default_model,
                "available_models": p.available_models or []
            })

    # Get default model
    default_model = None
    if app.default_model_profile_id:
        stmt = select(ChatModelProfile).where(
            ChatModelProfile.id == app.default_model_profile_id
        )
        result = await db.execute(stmt)
        default_profile = result.scalar_one_or_none()
        if default_profile:
            default_model = default_profile.default_model

    return PublicAppConfigResponse(
        name=app.name,
        description=app.description,
        welcome_message=app.welcome_message,
        allow_upload=app.allow_upload,
        allow_web_search=app.allow_web_search and settings.mcp.web_search_enabled,
        allow_model_selection=app.allow_model_selection,
        models=models,
        default_model=default_model,
        branding={
            "logo_url": app.logo_url,
            "primary_color": app.primary_color,
            "custom_css": app.custom_css
        }
    )


@router.post("/apps/{slug}/send")
async def public_send_message(
    slug: str,
    request: PublicSendRequest,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Send a message to a public app (streaming response)."""
    app = await get_public_app_from_token(slug, authorization, token, db)

    # Get or create conversation
    if request.conversation_id:
        conversation_id = UUID(request.conversation_id)

        # Verify conversation belongs to this app
        stmt = select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.public_app_id == app.id
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Check message limit
        if conversation.message_count >= app.max_messages_per_conversation:
            raise HTTPException(
                status_code=429,
                detail=f"Maximum {app.max_messages_per_conversation} messages per conversation"
            )
    else:
        # Create new conversation
        service = create_conversation_service(db, app.tenant_id, None)

        params = ConversationCreate(
            title="Public Chat",
            model_profile_id=app.default_model_profile_id,
            settings={
                "enable_web_search": app.allow_web_search and settings.mcp.web_search_enabled,
                "enable_doc_search": app.allow_doc_search,
                "system_prompt": app.system_prompt,
                **(app.model_params or {})
            }
        )

        conversation = await service.create_conversation(params)
        conversation.public_app_id = app.id
        await db.commit()
        conversation_id = conversation.id

    # Send message
    service = create_conversation_service(db, app.tenant_id, None)

    async def event_generator():
        # Include conversation ID in first event
        yield f"data: {json.dumps({'type': 'conversation', 'data': {'conversation_id': str(conversation_id)}})}\n\n"

        async for event in service.send_message(conversation_id, request.content):
            data = {
                "type": event.type,
                "data": event.data,
                "error": event.error
            }
            yield f"data: {json.dumps(data)}\n\n"

        yield "data: [DONE]\n\n"

    # Update app stats
    app.total_messages += 2  # User + assistant
    app.last_used_at = datetime.now(timezone.utc)
    if not request.conversation_id:
        app.total_conversations += 1
    await db.commit()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/apps/{slug}/upload")
async def public_upload_file(
    slug: str,
    conversation_id: str = Form(...),
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Upload a file to a public app conversation."""
    app = await get_public_app_from_token(slug, authorization, token, db)

    if not app.allow_upload:
        raise HTTPException(status_code=403, detail="File upload not allowed for this app")

    # Verify conversation
    stmt = select(ChatConversation).where(
        ChatConversation.id == UUID(conversation_id),
        ChatConversation.public_app_id == app.id
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Upload file
    content = await file.read()
    upload_service = create_upload_service(db, app.tenant_id)

    try:
        attachment = await upload_service.upload_file(
            conversation_id=UUID(conversation_id),
            file_name=file.filename or "unnamed",
            content=content,
            mime_type=file.content_type or "application/octet-stream",
            usage_mode="retrieval"
        )

        # Process in background
        asyncio.create_task(upload_service.process_document(attachment.id))

        return {
            "id": str(attachment.id),
            "file_name": attachment.file_name,
            "mime_type": attachment.mime_type,
            "size_bytes": attachment.size_bytes
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# OpenAI-Compatible Completions API
# =============================================================================

@router.post("/chat/completions")
async def openai_chat_completions(
    request: PublicChatRequest,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    OpenAI-compatible chat completions endpoint.

    This allows using the public app as an OpenAI-compatible API.
    The token in the Authorization header determines which app/profile to use.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization")

    token = authorization[7:]
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Find app by token
    stmt = select(ChatPublicApp).where(
        ChatPublicApp.token_hash == token_hash,
        ChatPublicApp.enabled == True
    )
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get model profile
    profile_service = ModelProfileService(db, app.tenant_id)
    client = await profile_service.create_client(profile_id=app.default_model_profile_id)

    # Convert messages
    messages = [
        OpenAIChatMessage(
            role=msg["role"],
            content=msg.get("content", "")
        )
        for msg in request.messages
    ]

    # Add system prompt if configured
    if app.system_prompt:
        messages.insert(0, OpenAIChatMessage(
            role="system",
            content=app.system_prompt
        ))

    # Build request
    chat_request = ChatCompletionRequest(
        model=request.model,
        messages=messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stream=request.stream
    )

    try:
        if request.stream:
            # Streaming response
            async def stream_generator():
                async for delta in client.chat_completions_stream(chat_request):
                    chunk = {
                        "id": f"chatcmpl-{secrets.token_hex(12)}",
                        "object": "chat.completion.chunk",
                        "created": int(datetime.now().timestamp()),
                        "model": request.model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": delta.finish_reason
                        }]
                    }

                    if delta.content:
                        chunk["choices"][0]["delta"]["content"] = delta.content

                    yield f"data: {json.dumps(chunk)}\n\n"

                yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream"
            )

        else:
            # Non-streaming response
            response = await client.chat_completions(chat_request)

            return {
                "id": response.id,
                "object": "chat.completion",
                "created": int(datetime.now().timestamp()),
                "model": response.model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response.content
                    },
                    "finish_reason": response.finish_reason
                }],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }

    finally:
        await client.close()
