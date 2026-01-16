"""
Chat/Playground Database Models.

This module contains all database models for the Chat/Playground module:
- ChatModelProfile: Model configuration profiles
- ChatConversation: Conversation metadata
- ChatMessage: Individual chat messages
- ChatAttachment: File attachments for conversations
- ChatDocChunk: Document chunks for RAG
- ChatDocEmbedding: Vector embeddings for document search
- ChatPublicApp: Public chat application configurations
- ChatMCPServer: MCP server configurations
- ChatMCPToolCall: MCP tool call audit logs

Reference documentation:
- OpenAI Chat API: https://platform.openai.com/docs/api-reference/chat
- MCP Protocol: https://modelcontextprotocol.io/
"""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


# =============================================================================
# Enums
# =============================================================================

class MessageRole(str, enum.Enum):
    """Chat message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class MCPTransport(str, enum.Enum):
    """MCP server transport types."""

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"


class MCPServerStatus(str, enum.Enum):
    """MCP server health status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


# =============================================================================
# Models
# =============================================================================

class ChatModelProfile(Base):
    """
    Model configuration profile.

    A model profile defines a connection to an AI model endpoint,
    which can be:
    - The platform's internal gateway (/v1)
    - External services (OpenAI, Anthropic, etc.)
    - User's own deployments (vLLM, SGLang, etc.)
    """

    __tablename__ = "chat_model_profiles"
    __table_args__ = (
        Index("ix_chat_model_profiles_tenant_id", "tenant_id"),
        Index("ix_chat_model_profiles_enabled", "enabled"),
        UniqueConstraint("tenant_id", "name", name="uq_chat_model_profiles_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Profile identification
    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    # Connection configuration
    base_url = Column(String(2000), nullable=False)

    # Optional API key reference
    api_key_secret_id = Column(
        UUID(as_uuid=True),
        ForeignKey("gateway_secrets.id", ondelete="SET NULL")
    )

    # Default model
    default_model = Column(String(255), nullable=False)
    available_models = Column(ARRAY(String), default=list)

    # Capabilities
    capabilities = Column(ARRAY(String), default=list)

    # Custom headers
    headers = Column(JSONB, default=dict)

    # Default parameters
    default_params = Column(JSONB, default=dict)

    # Connection settings
    timeout_ms = Column(Integer, default=120000)
    max_retries = Column(Integer, default=2)

    # Status
    enabled = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    api_key_secret = relationship("GatewaySecret")
    conversations = relationship("ChatConversation", back_populates="model_profile")

    def __repr__(self):
        return f"<ChatModelProfile(id={self.id}, name={self.name})>"


class ChatConversation(Base):
    """
    Chat conversation metadata.

    A conversation groups related messages together and maintains
    state like the active model, settings, and ownership.
    """

    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("ix_chat_conversations_tenant_id", "tenant_id"),
        Index("ix_chat_conversations_owner_user_id", "owner_user_id"),
        Index("ix_chat_conversations_public_app_id", "public_app_id"),
        Index("ix_chat_conversations_pinned", "pinned"),
        Index("ix_chat_conversations_is_deleted", "is_deleted"),
        Index("ix_chat_conversations_created_at", "created_at"),
        Index("ix_chat_conversations_user_list",
              "owner_user_id", "is_deleted", "pinned", "updated_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Owner (nullable for public apps)
    owner_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # Metadata
    title = Column(String(500), default="New Conversation")
    pinned = Column(Boolean, default=False, nullable=False)

    # Active model profile
    active_model_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_model_profiles.id", ondelete="SET NULL")
    )
    active_model = Column(String(255))

    # Settings
    settings = Column(JSONB, default=dict)

    # For public apps
    public_app_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_public_apps.id", ondelete="SET NULL")
    )

    # Stats
    message_count = Column(Integer, default=0)
    last_message_at = Column(DateTime(timezone=True))
    total_prompt_tokens = Column(Integer, default=0)
    total_completion_tokens = Column(Integer, default=0)

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True))

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", backref="chat_conversations")
    model_profile = relationship("ChatModelProfile", back_populates="conversations")
    public_app = relationship("ChatPublicApp", back_populates="conversations")
    messages = relationship("ChatMessage", back_populates="conversation",
                            cascade="all, delete-orphan")
    attachments = relationship("ChatAttachment", back_populates="conversation",
                               cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatConversation(id={self.id}, title={self.title})>"


class ChatMessage(Base):
    """
    Individual chat message.

    Stores the message content, role, and associated metadata.
    Supports multimodal content and tool calls.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_conversation_id", "conversation_id"),
        Index("ix_chat_messages_role", "role"),
        Index("ix_chat_messages_is_active", "is_active"),
        Index("ix_chat_messages_created_at", "created_at"),
        Index("ix_chat_messages_parent_message_id", "parent_message_id"),
        Index("ix_chat_messages_conv_active",
              "conversation_id", "is_active", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False
    )

    # Role
    role = Column(Enum(MessageRole), nullable=False)

    # Content (structured)
    content = Column(JSONB, nullable=False)

    # Tool data
    tool_data = Column(JSONB)

    # Model info
    model = Column(String(255))
    model_profile_id = Column(UUID(as_uuid=True))

    # Token usage
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)

    # Metadata
    message_metadata = Column(JSONB, default=dict)

    # Regeneration tracking
    parent_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Feedback
    feedback_rating = Column(Integer)
    feedback_comment = Column(Text)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    conversation = relationship("ChatConversation", back_populates="messages")
    parent_message = relationship("ChatMessage", remote_side=[id])
    attachments = relationship("ChatAttachment", back_populates="message")

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, role={self.role.value})>"

    @property
    def text_content(self) -> str:
        """Extract text content from structured content."""
        if isinstance(self.content, dict):
            if self.content.get("type") == "text":
                return self.content.get("text", "")
            elif self.content.get("type") == "multimodal":
                parts = self.content.get("parts", [])
                texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
                return "\n".join(texts)
        return str(self.content)


class ChatAttachment(Base):
    """
    File attachment for a conversation.

    Stores file metadata and references to MinIO storage.
    Supports text extraction and chunking for RAG.
    """

    __tablename__ = "chat_attachments"
    __table_args__ = (
        Index("ix_chat_attachments_conversation_id", "conversation_id"),
        Index("ix_chat_attachments_message_id", "message_id"),
        Index("ix_chat_attachments_mime_type", "mime_type"),
        Index("ix_chat_attachments_extraction_status", "extraction_status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False
    )

    # Optional message association
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="SET NULL")
    )

    # File metadata
    file_name = Column(String(500), nullable=False)
    original_name = Column(String(500))
    mime_type = Column(String(255), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)

    # MinIO storage
    minio_bucket = Column(String(255), nullable=False)
    minio_key = Column(String(1000), nullable=False)

    # Integrity
    sha256 = Column(String(64))

    # Text extraction
    extracted_text_ref = Column(String(1000))
    extraction_status = Column(String(50), default="pending")
    extraction_error = Column(Text)

    # Document processing
    chunk_count = Column(Integer, default=0)
    embedding_status = Column(String(50), default="pending")

    # Usage mode
    usage_mode = Column(String(50), default="retrieval")

    # Audit
    uploaded_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    conversation = relationship("ChatConversation", back_populates="attachments")
    message = relationship("ChatMessage", back_populates="attachments")
    chunks = relationship("ChatDocChunk", back_populates="attachment",
                          cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatAttachment(id={self.id}, file_name={self.file_name})>"


class ChatDocChunk(Base):
    """
    Document chunk for RAG.

    Splits documents into smaller chunks for embedding and retrieval.
    """

    __tablename__ = "chat_doc_chunks"
    __table_args__ = (
        Index("ix_chat_doc_chunks_attachment_id", "attachment_id"),
        Index("ix_chat_doc_chunks_chunk_index", "chunk_index"),
        UniqueConstraint("attachment_id", "chunk_index",
                         name="uq_chat_doc_chunks_attachment_index"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attachment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_attachments.id", ondelete="CASCADE"),
        nullable=False
    )

    # Chunk identification
    chunk_index = Column(Integer, nullable=False)

    # Content
    content = Column(Text, nullable=False)
    char_count = Column(Integer)
    token_count = Column(Integer)

    # Position in source
    start_char = Column(Integer)
    end_char = Column(Integer)
    page_number = Column(Integer)

    # Metadata for citations
    chunk_metadata = Column(JSONB, default=dict)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    attachment = relationship("ChatAttachment", back_populates="chunks")
    embeddings = relationship("ChatDocEmbedding", back_populates="chunk",
                              cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatDocChunk(id={self.id}, chunk_index={self.chunk_index})>"


class ChatDocEmbedding(Base):
    """
    Vector embedding for document chunk.

    Stores embeddings for semantic search.
    """

    __tablename__ = "chat_doc_embeddings"
    __table_args__ = (
        Index("ix_chat_doc_embeddings_chunk_id", "chunk_id"),
        Index("ix_chat_doc_embeddings_model_profile_id", "model_profile_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_doc_chunks.id", ondelete="CASCADE"),
        nullable=False
    )

    # Embedding vector (stored as float array)
    embedding = Column(ARRAY(Float))

    # Model info
    model_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_model_profiles.id", ondelete="SET NULL")
    )
    embedding_model = Column(String(255))
    embedding_dimensions = Column(Integer)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    chunk = relationship("ChatDocChunk", back_populates="embeddings")
    model_profile = relationship("ChatModelProfile")

    def __repr__(self):
        return f"<ChatDocEmbedding(id={self.id}, chunk_id={self.chunk_id})>"


class ChatPublicApp(Base):
    """
    Public chat application configuration.

    Allows creating shareable chat interfaces with custom settings,
    branding, and access controls.
    """

    __tablename__ = "chat_public_apps"
    __table_args__ = (
        Index("ix_chat_public_apps_tenant_id", "tenant_id"),
        Index("ix_chat_public_apps_enabled", "enabled"),
        UniqueConstraint("slug", name="uq_chat_public_apps_slug"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # URL slug
    slug = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(2000))
    welcome_message = Column(Text)

    # Access token (hashed)
    token_hash = Column(String(255), nullable=False)
    token_prefix = Column(String(12))

    # Model configuration
    allowed_model_profile_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)
    default_model_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_model_profiles.id", ondelete="SET NULL")
    )

    # Feature toggles
    allow_upload = Column(Boolean, default=False, nullable=False)
    allow_web_search = Column(Boolean, default=False, nullable=False)
    allow_doc_search = Column(Boolean, default=True, nullable=False)
    allow_model_selection = Column(Boolean, default=False, nullable=False)

    # Constraints
    max_file_size_mb = Column(Integer, default=10)
    max_files_per_conversation = Column(Integer, default=10)
    max_messages_per_conversation = Column(Integer, default=100)
    max_conversations_per_token = Column(Integer, default=10)

    # Rate limiting
    rate_limit = Column(JSONB, default=dict)

    # System prompt override
    system_prompt = Column(Text)
    model_params = Column(JSONB, default=dict)

    # Branding
    logo_url = Column(String(2000))
    primary_color = Column(String(7))
    custom_css = Column(Text)

    # Access control
    expires_at = Column(DateTime(timezone=True))
    enabled = Column(Boolean, default=True, nullable=False)

    # Analytics
    total_conversations = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True))

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    default_model_profile = relationship("ChatModelProfile")
    conversations = relationship("ChatConversation", back_populates="public_app")

    def __repr__(self):
        return f"<ChatPublicApp(id={self.id}, slug={self.slug})>"


class ChatMCPServer(Base):
    """
    MCP server configuration.

    Defines how to connect to an MCP server for tool execution.
    """

    __tablename__ = "chat_mcp_servers"
    __table_args__ = (
        Index("ix_chat_mcp_servers_tenant_id", "tenant_id"),
        Index("ix_chat_mcp_servers_enabled", "enabled"),
        Index("ix_chat_mcp_servers_transport", "transport"),
        UniqueConstraint("tenant_id", "name", name="uq_chat_mcp_servers_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Identification
    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    # Transport
    transport = Column(Enum(MCPTransport), nullable=False)
    connection_config = Column(JSONB, nullable=False)
    environment = Column(JSONB, default=dict)

    # Capabilities
    capabilities = Column(JSONB, default=dict)
    tools_cache = Column(JSONB, default=list)
    tools_cache_updated_at = Column(DateTime(timezone=True))

    # Security
    allowed_tools = Column(ARRAY(String), default=list)
    rate_limit = Column(JSONB, default=dict)

    # Status
    status = Column(Enum(MCPServerStatus), default=MCPServerStatus.INACTIVE)
    last_health_check = Column(DateTime(timezone=True))
    health_check_error = Column(Text)

    # Display
    display_order = Column(Integer, default=100)
    enabled = Column(Boolean, default=True, nullable=False)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    tool_calls = relationship("ChatMCPToolCall", back_populates="mcp_server")

    def __repr__(self):
        return f"<ChatMCPServer(id={self.id}, name={self.name})>"


class ChatMCPToolCall(Base):
    """
    MCP tool call audit log.

    Records all tool calls for security auditing and debugging.
    """

    __tablename__ = "chat_mcp_tool_calls"
    __table_args__ = (
        Index("ix_chat_mcp_tool_calls_tenant_id", "tenant_id"),
        Index("ix_chat_mcp_tool_calls_conversation_id", "conversation_id"),
        Index("ix_chat_mcp_tool_calls_user_id", "user_id"),
        Index("ix_chat_mcp_tool_calls_mcp_server_id", "mcp_server_id"),
        Index("ix_chat_mcp_tool_calls_tool_name", "tool_name"),
        Index("ix_chat_mcp_tool_calls_status", "status"),
        Index("ix_chat_mcp_tool_calls_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Context
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="SET NULL")
    )
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # MCP server
    mcp_server_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_mcp_servers.id", ondelete="SET NULL")
    )
    mcp_server_name = Column(String(255))

    # Tool call details
    tool_name = Column(String(255), nullable=False)
    tool_call_id = Column(String(255))

    # Arguments
    arguments = Column(JSONB)
    arguments_redacted = Column(Boolean, default=False)

    # Result
    result = Column(JSONB)
    result_truncated = Column(Boolean, default=False)

    # Status
    status = Column(String(50), nullable=False)
    error_message = Column(Text)

    # Timing
    latency_ms = Column(Integer)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    conversation = relationship("ChatConversation")
    message = relationship("ChatMessage")
    user = relationship("User")
    mcp_server = relationship("ChatMCPServer", back_populates="tool_calls")

    def __repr__(self):
        return f"<ChatMCPToolCall(id={self.id}, tool_name={self.tool_name})>"
