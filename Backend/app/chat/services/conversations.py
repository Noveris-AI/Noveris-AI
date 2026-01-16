"""
Chat Conversation Service.

This module provides the core business logic for chat conversations:
- Creating and managing conversations
- Sending messages and receiving responses
- Streaming chat completions
- Tool call handling
- Token usage tracking

References:
- OpenAI Chat API: https://platform.openai.com/docs/api-reference/chat
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.chat import (
    ChatConversation,
    ChatMessage,
    ChatModelProfile,
    ChatAttachment,
    MessageRole,
)
from app.chat.services.openai_client import (
    OpenAIClient,
    ChatCompletionRequest,
    ChatMessage as OpenAIChatMessage,
    ChatCompletionResponse,
    StreamDelta,
    TokenUsage,
    ModelProfileService,
)
from app.chat.services.mcp_client import MCPClientManager, get_mcp_client

logger = logging.getLogger(__name__)


# =============================================================================
# Schemas
# =============================================================================

class ConversationCreate:
    """Parameters for creating a conversation."""
    def __init__(
        self,
        title: Optional[str] = None,
        model_profile_id: Optional[UUID] = None,
        model: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None
    ):
        self.title = title
        self.model_profile_id = model_profile_id
        self.model = model
        self.settings = settings or {}


class MessageCreate:
    """Parameters for creating a message."""
    def __init__(
        self,
        content: Union[str, Dict[str, Any]],
        role: MessageRole = MessageRole.USER,
        attachment_ids: Optional[List[UUID]] = None
    ):
        self.content = content
        self.role = role
        self.attachment_ids = attachment_ids or []


class StreamEvent:
    """Event emitted during streaming."""
    def __init__(
        self,
        type: str,
        data: Any = None,
        error: Optional[str] = None
    ):
        self.type = type  # "start", "delta", "tool_call", "tool_result", "done", "error"
        self.data = data
        self.error = error


# =============================================================================
# Conversation Service
# =============================================================================

class ConversationService:
    """
    Service for managing chat conversations.

    Handles conversation CRUD, message management, and chat completions.
    """

    def __init__(self, db: AsyncSession, tenant_id: UUID, user_id: Optional[UUID] = None):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id

    # -------------------------------------------------------------------------
    # Conversation CRUD
    # -------------------------------------------------------------------------

    async def create_conversation(
        self,
        params: ConversationCreate
    ) -> ChatConversation:
        """Create a new conversation."""
        # Get model profile
        profile_service = ModelProfileService(self.db, self.tenant_id)

        if params.model_profile_id:
            profile = await profile_service.get_profile(params.model_profile_id)
        else:
            profile = await profile_service.get_default_profile()

        model = params.model or (profile.default_model if profile else None)

        conversation = ChatConversation(
            tenant_id=self.tenant_id,
            owner_user_id=self.user_id,
            title=params.title or "New Conversation",
            active_model_profile_id=profile.id if profile else None,
            active_model=model,
            settings=self._build_default_settings(params.settings, profile),
        )

        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)

        return conversation

    def _build_default_settings(
        self,
        user_settings: Optional[Dict[str, Any]],
        profile: Optional[ChatModelProfile]
    ) -> Dict[str, Any]:
        """Build conversation settings with defaults."""
        defaults = {
            "enable_web_search": settings.mcp.web_search_enabled,
            "enable_doc_search": True,
            "system_prompt": None,
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 1.0,
            "presence_penalty": 0,
            "frequency_penalty": 0,
        }

        # Merge profile defaults
        if profile and profile.default_params:
            defaults.update(profile.default_params)

        # Merge user settings
        if user_settings:
            defaults.update(user_settings)

        return defaults

    async def get_conversation(
        self,
        conversation_id: UUID,
        load_messages: bool = False
    ) -> Optional[ChatConversation]:
        """Get a conversation by ID."""
        stmt = select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.tenant_id == self.tenant_id,
            ChatConversation.is_deleted == False
        )

        if load_messages:
            stmt = stmt.options(selectinload(ChatConversation.messages))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None
    ) -> Tuple[List[ChatConversation], int]:
        """List conversations for the current user."""
        base_stmt = select(ChatConversation).where(
            ChatConversation.tenant_id == self.tenant_id,
            ChatConversation.owner_user_id == self.user_id,
            ChatConversation.is_deleted == False
        )

        if search:
            base_stmt = base_stmt.where(
                ChatConversation.title.ilike(f"%{search}%")
            )

        # Get total count
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get paginated results
        stmt = base_stmt.order_by(
            ChatConversation.pinned.desc(),
            ChatConversation.updated_at.desc()
        ).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        conversations = list(result.scalars().all())

        return conversations, total

    async def update_conversation(
        self,
        conversation_id: UUID,
        title: Optional[str] = None,
        pinned: Optional[bool] = None,
        model_profile_id: Optional[UUID] = None,
        model: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> Optional[ChatConversation]:
        """Update a conversation."""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return None

        if title is not None:
            conversation.title = title[:settings.chat.conversation_title_max_length]
        if pinned is not None:
            conversation.pinned = pinned
        if model_profile_id is not None:
            conversation.active_model_profile_id = model_profile_id
        if model is not None:
            conversation.active_model = model
        if settings is not None:
            conversation.settings = {**conversation.settings, **settings}

        await self.db.commit()
        await self.db.refresh(conversation)

        return conversation

    async def delete_conversation(self, conversation_id: UUID) -> bool:
        """Soft delete a conversation."""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return False

        conversation.is_deleted = True
        conversation.deleted_at = datetime.now(timezone.utc)

        await self.db.commit()
        return True

    # -------------------------------------------------------------------------
    # Message Management
    # -------------------------------------------------------------------------

    async def get_messages(
        self,
        conversation_id: UUID,
        limit: int = 100,
        before_id: Optional[UUID] = None
    ) -> List[ChatMessage]:
        """Get messages for a conversation."""
        stmt = select(ChatMessage).where(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.is_active == True
        )

        if before_id:
            stmt = stmt.where(ChatMessage.id < before_id)

        stmt = stmt.order_by(ChatMessage.created_at.desc()).limit(limit)

        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())

        # Return in chronological order
        messages.reverse()
        return messages

    async def add_message(
        self,
        conversation_id: UUID,
        params: MessageCreate
    ) -> ChatMessage:
        """Add a message to a conversation."""
        # Format content
        if isinstance(params.content, str):
            content = {"type": "text", "text": params.content}
        else:
            content = params.content

        message = ChatMessage(
            conversation_id=conversation_id,
            role=params.role,
            content=content,
        )

        self.db.add(message)

        # Update conversation stats
        await self.db.execute(
            update(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .values(
                message_count=ChatConversation.message_count + 1,
                last_message_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
        )

        await self.db.commit()
        await self.db.refresh(message)

        # Link attachments if provided
        if params.attachment_ids:
            await self.db.execute(
                update(ChatAttachment)
                .where(ChatAttachment.id.in_(params.attachment_ids))
                .values(message_id=message.id)
            )
            await self.db.commit()

        return message

    # -------------------------------------------------------------------------
    # Chat Completion
    # -------------------------------------------------------------------------

    async def send_message(
        self,
        conversation_id: UUID,
        content: Union[str, Dict[str, Any]],
        attachment_ids: Optional[List[UUID]] = None
    ) -> AsyncIterator[StreamEvent]:
        """
        Send a message and get streaming response.

        This is the main entry point for chat interactions. It:
        1. Adds the user message
        2. Builds the context
        3. Calls the model (with tool support)
        4. Streams the response
        5. Handles tool calls

        Yields:
            StreamEvent objects during the interaction
        """
        # Get conversation
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            yield StreamEvent(type="error", error="Conversation not found")
            return

        # Add user message
        user_message = await self.add_message(
            conversation_id,
            MessageCreate(content=content, role=MessageRole.USER, attachment_ids=attachment_ids)
        )

        yield StreamEvent(type="start", data={"message_id": str(user_message.id)})

        try:
            # Build messages for API
            messages = await self._build_messages_for_api(conversation)

            # Get model client
            profile_service = ModelProfileService(self.db, self.tenant_id)
            client = await profile_service.create_client(
                profile_id=conversation.active_model_profile_id
            )

            # Get tools if enabled
            tools = None
            if conversation.settings.get("enable_web_search") or conversation.settings.get("enable_doc_search"):
                async with get_mcp_client(self.db, self.tenant_id) as mcp:
                    tools = await mcp.get_tools_for_openai()

            # Build request
            request = ChatCompletionRequest(
                model=conversation.active_model or client.model_profile.default_model,
                messages=messages,
                temperature=conversation.settings.get("temperature", 0.7),
                max_tokens=conversation.settings.get("max_tokens"),
                top_p=conversation.settings.get("top_p", 1.0),
                stream=True,
                tools=tools if tools else None,
            )

            # Stream response
            assistant_content = ""
            tool_calls_data = []
            usage = TokenUsage()

            async for delta in client.chat_completions_stream(request):
                if delta.content:
                    assistant_content += delta.content
                    yield StreamEvent(type="delta", data={"content": delta.content})

                if delta.tool_calls:
                    tool_calls_data.extend(delta.tool_calls)
                    yield StreamEvent(type="tool_call", data={"tool_calls": delta.tool_calls})

                if delta.finish_reason:
                    yield StreamEvent(type="finish", data={"reason": delta.finish_reason})

            # Handle tool calls if any
            if tool_calls_data:
                async for event in self._handle_tool_calls(
                    conversation, messages, tool_calls_data, client
                ):
                    yield event
                    if event.type == "delta":
                        assistant_content += event.data.get("content", "")

            # Save assistant message
            assistant_message = await self._save_assistant_message(
                conversation_id,
                assistant_content,
                tool_calls_data,
                usage,
                client.model_profile
            )

            yield StreamEvent(
                type="done",
                data={
                    "message_id": str(assistant_message.id),
                    "usage": {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens
                    }
                }
            )

            await client.close()

        except Exception as e:
            logger.error(f"Chat completion error: {e}")
            yield StreamEvent(type="error", error=str(e))

    async def _build_messages_for_api(
        self,
        conversation: ChatConversation
    ) -> List[OpenAIChatMessage]:
        """Build message list for API request."""
        messages = []

        # Add system prompt if configured
        system_prompt = conversation.settings.get("system_prompt")
        if system_prompt:
            messages.append(OpenAIChatMessage(
                role="system",
                content=system_prompt
            ))

        # Get conversation messages
        db_messages = await self.get_messages(conversation.id, limit=100)

        for msg in db_messages:
            content = msg.content
            if isinstance(content, dict) and content.get("type") == "text":
                content = content.get("text", "")

            api_msg = OpenAIChatMessage(
                role=msg.role.value,
                content=content
            )

            if msg.tool_data:
                if msg.role == MessageRole.TOOL:
                    api_msg.tool_call_id = msg.tool_data.get("tool_call_id")
                elif msg.role == MessageRole.ASSISTANT:
                    api_msg.tool_calls = msg.tool_data.get("tool_calls")

            messages.append(api_msg)

        return messages

    async def _handle_tool_calls(
        self,
        conversation: ChatConversation,
        messages: List[OpenAIChatMessage],
        tool_calls: List[Dict[str, Any]],
        client: OpenAIClient
    ) -> AsyncIterator[StreamEvent]:
        """Handle tool calls from the model."""
        async with get_mcp_client(self.db, self.tenant_id) as mcp:
            # Execute each tool call
            tool_results = []

            for tc in tool_calls:
                tc_id = tc.get("id")
                function = tc.get("function", {})
                name = function.get("name", "")
                args_str = function.get("arguments", "{}")

                try:
                    arguments = json.loads(args_str)
                except json.JSONDecodeError:
                    arguments = {}

                yield StreamEvent(
                    type="tool_call",
                    data={"tool_name": name, "arguments": arguments}
                )

                # Call the tool
                result = await mcp.call_tool(
                    name,
                    arguments,
                    context={
                        "conversation_id": conversation.id,
                        "user_id": self.user_id
                    }
                )

                tool_results.append({
                    "tool_call_id": tc_id,
                    "role": "tool",
                    "content": json.dumps(result.content) if isinstance(result.content, dict) else str(result.content or result.error)
                })

                yield StreamEvent(
                    type="tool_result",
                    data={"tool_call_id": tc_id, "result": result.content}
                )

            # Add tool results to messages and get follow-up response
            messages.append(OpenAIChatMessage(
                role="assistant",
                content="",
                tool_calls=tool_calls
            ))

            for tr in tool_results:
                messages.append(OpenAIChatMessage(
                    role="tool",
                    content=tr["content"],
                    tool_call_id=tr["tool_call_id"]
                ))

            # Get follow-up response
            request = ChatCompletionRequest(
                model=conversation.active_model or client.model_profile.default_model,
                messages=messages,
                temperature=conversation.settings.get("temperature", 0.7),
                max_tokens=conversation.settings.get("max_tokens"),
                stream=True
            )

            async for delta in client.chat_completions_stream(request):
                if delta.content:
                    yield StreamEvent(type="delta", data={"content": delta.content})

    async def _save_assistant_message(
        self,
        conversation_id: UUID,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]],
        usage: TokenUsage,
        profile: ChatModelProfile
    ) -> ChatMessage:
        """Save assistant message to database."""
        message = ChatMessage(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content={"type": "text", "text": content},
            model=profile.default_model,
            model_profile_id=profile.id,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            tool_data={"tool_calls": tool_calls} if tool_calls else None
        )

        self.db.add(message)

        # Update conversation token usage
        await self.db.execute(
            update(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .values(
                message_count=ChatConversation.message_count + 1,
                last_message_at=datetime.now(timezone.utc),
                total_prompt_tokens=ChatConversation.total_prompt_tokens + usage.prompt_tokens,
                total_completion_tokens=ChatConversation.total_completion_tokens + usage.completion_tokens,
                updated_at=datetime.now(timezone.utc)
            )
        )

        await self.db.commit()
        await self.db.refresh(message)

        return message

    # -------------------------------------------------------------------------
    # Regeneration
    # -------------------------------------------------------------------------

    async def regenerate_message(
        self,
        conversation_id: UUID,
        message_id: UUID
    ) -> AsyncIterator[StreamEvent]:
        """Regenerate a response from a specific message."""
        # Mark the message as inactive
        await self.db.execute(
            update(ChatMessage)
            .where(ChatMessage.id == message_id)
            .values(is_active=False)
        )
        await self.db.commit()

        # Get the conversation and find the last user message before this one
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            yield StreamEvent(type="error", error="Conversation not found")
            return

        # Get messages up to the one before the regenerated message
        stmt = select(ChatMessage).where(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.is_active == True,
            ChatMessage.created_at < (
                select(ChatMessage.created_at)
                .where(ChatMessage.id == message_id)
                .scalar_subquery()
            )
        ).order_by(ChatMessage.created_at.desc()).limit(1)

        result = await self.db.execute(stmt)
        last_user_msg = result.scalar_one_or_none()

        if not last_user_msg:
            yield StreamEvent(type="error", error="No previous message found")
            return

        # Re-send from that message
        content = last_user_msg.content
        if isinstance(content, dict):
            content = content.get("text", "")

        async for event in self.send_message(conversation_id, content):
            yield event


# =============================================================================
# Factory Function
# =============================================================================

def create_conversation_service(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: Optional[UUID] = None
) -> ConversationService:
    """Create a conversation service instance."""
    return ConversationService(db, tenant_id, user_id)
