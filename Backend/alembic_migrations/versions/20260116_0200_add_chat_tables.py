"""Add Chat/Playground tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-16 02:00:00.000000

This migration creates tables for the Chat/Playground module:
- chat_model_profiles: Model configuration profiles
- chat_conversations: Chat conversation metadata
- chat_messages: Individual chat messages
- chat_attachments: File attachments for conversations
- chat_doc_chunks: Document chunks for RAG
- chat_doc_embeddings: Vector embeddings for document search
- chat_public_apps: Public chat application configurations
- chat_mcp_servers: MCP server configurations
- chat_mcp_tool_calls: MCP tool call audit logs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types using DO blocks to handle partial migration recovery
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE chat_message_role AS ENUM (
                'user',
                'assistant',
                'tool',
                'system'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE chat_mcp_transport AS ENUM (
                'stdio',
                'sse',
                'streamable_http'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE chat_mcp_server_status AS ENUM (
                'active',
                'inactive',
                'error'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # =========================================================================
    # chat_model_profiles - Model configuration profiles
    # =========================================================================
    op.create_table(
        'chat_model_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Profile identification
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000)),

        # Connection configuration
        # base_url can point to:
        # - Internal gateway: /v1 (relative to platform)
        # - External service: https://api.openai.com/v1
        # - User's own service: http://192.168.1.100:8000/v1
        sa.Column('base_url', sa.String(2000), nullable=False),

        # Optional API key - references gateway_secrets for encryption
        # Can be null for internal services that don't require auth
        sa.Column('api_key_secret_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('gateway_secrets.id', ondelete='SET NULL')),

        # Default model to use when user doesn't specify
        # e.g., "gpt-4o", "claude-3-5-sonnet", "local-llama"
        sa.Column('default_model', sa.String(255), nullable=False),

        # Available models (fetched from /v1/models or manually configured)
        # Format: ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet"]
        sa.Column('available_models', postgresql.ARRAY(sa.String), default=list),

        # Capabilities this profile supports
        # Values: chat_completions, completions, responses, embeddings,
        #         images_generations, audio_speech, audio_transcriptions, rerank
        sa.Column('capabilities', postgresql.ARRAY(sa.String), default=list),

        # Custom headers to inject (e.g., for custom auth schemes)
        # Format: {"X-Custom-Header": "value"}
        sa.Column('headers', postgresql.JSONB, default=dict),

        # Model parameters defaults
        # Format: {"temperature": 0.7, "max_tokens": 4096, "top_p": 1.0}
        sa.Column('default_params', postgresql.JSONB, default=dict),

        # Connection settings
        sa.Column('timeout_ms', sa.Integer, default=120000),
        sa.Column('max_retries', sa.Integer, default=2),

        # Status
        sa.Column('enabled', sa.Boolean, default=True, nullable=False),
        sa.Column('is_default', sa.Boolean, default=False, nullable=False),

        # Audit
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_chat_model_profiles_tenant_id', 'chat_model_profiles', ['tenant_id'])
    op.create_index('ix_chat_model_profiles_enabled', 'chat_model_profiles', ['enabled'])
    op.create_unique_constraint('uq_chat_model_profiles_tenant_name', 'chat_model_profiles',
                                ['tenant_id', 'name'])

    # =========================================================================
    # chat_conversations - Chat conversation metadata
    # =========================================================================
    op.create_table(
        'chat_conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Owner (nullable for public apps)
        sa.Column('owner_user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL')),

        # Conversation metadata
        sa.Column('title', sa.String(500), default='New Conversation'),
        sa.Column('pinned', sa.Boolean, default=False, nullable=False),

        # Active model profile for this conversation
        sa.Column('active_model_profile_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_model_profiles.id', ondelete='SET NULL')),

        # Currently selected model within the profile
        sa.Column('active_model', sa.String(255)),

        # Conversation settings
        # Format: {
        #   "enable_web_search": true,
        #   "enable_doc_search": true,
        #   "system_prompt": "You are a helpful assistant.",
        #   "temperature": 0.7,
        #   "max_tokens": 4096,
        #   "top_p": 1.0,
        #   "presence_penalty": 0,
        #   "frequency_penalty": 0,
        #   "tools_enabled": ["web_search", "doc_search"],
        #   "response_format": null
        # }
        sa.Column('settings', postgresql.JSONB, default=dict),

        # For public apps - links to public_app
        sa.Column('public_app_id', postgresql.UUID(as_uuid=True)),

        # Message count for quick stats
        sa.Column('message_count', sa.Integer, default=0),
        sa.Column('last_message_at', sa.DateTime(timezone=True)),

        # Token usage tracking
        sa.Column('total_prompt_tokens', sa.Integer, default=0),
        sa.Column('total_completion_tokens', sa.Integer, default=0),

        # Soft delete
        sa.Column('is_deleted', sa.Boolean, default=False, nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_chat_conversations_tenant_id', 'chat_conversations', ['tenant_id'])
    op.create_index('ix_chat_conversations_owner_user_id', 'chat_conversations', ['owner_user_id'])
    op.create_index('ix_chat_conversations_public_app_id', 'chat_conversations', ['public_app_id'])
    op.create_index('ix_chat_conversations_pinned', 'chat_conversations', ['pinned'])
    op.create_index('ix_chat_conversations_is_deleted', 'chat_conversations', ['is_deleted'])
    op.create_index('ix_chat_conversations_created_at', 'chat_conversations', ['created_at'])

    # Composite index for user's conversation list
    op.create_index('ix_chat_conversations_user_list',
                    'chat_conversations', ['owner_user_id', 'is_deleted', 'pinned', 'updated_at'])

    # =========================================================================
    # chat_messages - Individual chat messages
    # =========================================================================
    op.create_table(
        'chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_conversations.id', ondelete='CASCADE'), nullable=False),

        # Message role
        sa.Column('role', sa.Enum(
            'user', 'assistant', 'tool', 'system',
            name='chat_message_role', create_type=False
        ), nullable=False),

        # Content - can be text or structured multimodal content
        # For simple text: {"type": "text", "text": "Hello"}
        # For multimodal: {"type": "multimodal", "parts": [
        #   {"type": "text", "text": "What's in this image?"},
        #   {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
        # ]}
        sa.Column('content', postgresql.JSONB, nullable=False),

        # For tool calls/results
        # Tool call: {"tool_calls": [{"id": "call_123", "type": "function",
        #             "function": {"name": "search", "arguments": "{...}"}}]}
        # Tool result: {"tool_call_id": "call_123", "content": "..."}
        sa.Column('tool_data', postgresql.JSONB),

        # Model that generated this message (for assistant messages)
        sa.Column('model', sa.String(255)),
        sa.Column('model_profile_id', postgresql.UUID(as_uuid=True)),

        # Token usage for this message
        sa.Column('prompt_tokens', sa.Integer),
        sa.Column('completion_tokens', sa.Integer),

        # Generation metadata
        # Format: {"finish_reason": "stop", "system_fingerprint": "..."}
        sa.Column('metadata', postgresql.JSONB, default=dict),

        # For regeneration tracking
        sa.Column('parent_message_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_messages.id', ondelete='SET NULL')),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),

        # Feedback
        sa.Column('feedback_rating', sa.Integer),  # 1-5 or thumbs up/down
        sa.Column('feedback_comment', sa.Text),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_chat_messages_conversation_id', 'chat_messages', ['conversation_id'])
    op.create_index('ix_chat_messages_role', 'chat_messages', ['role'])
    op.create_index('ix_chat_messages_is_active', 'chat_messages', ['is_active'])
    op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])
    op.create_index('ix_chat_messages_parent_message_id', 'chat_messages', ['parent_message_id'])

    # Composite index for conversation message list
    op.create_index('ix_chat_messages_conv_active',
                    'chat_messages', ['conversation_id', 'is_active', 'created_at'])

    # =========================================================================
    # chat_attachments - File attachments for conversations
    # =========================================================================
    op.create_table(
        'chat_attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_conversations.id', ondelete='CASCADE'), nullable=False),

        # Optional message association (attached before sending)
        sa.Column('message_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_messages.id', ondelete='SET NULL')),

        # File metadata
        sa.Column('file_name', sa.String(500), nullable=False),
        sa.Column('original_name', sa.String(500)),  # User's original filename
        sa.Column('mime_type', sa.String(255), nullable=False),
        sa.Column('size_bytes', sa.BigInteger, nullable=False),

        # MinIO storage reference
        sa.Column('minio_bucket', sa.String(255), nullable=False),
        sa.Column('minio_key', sa.String(1000), nullable=False),

        # Integrity
        sa.Column('sha256', sa.String(64)),

        # For documents: reference to extracted text
        # Points to a text file in MinIO or inline storage
        sa.Column('extracted_text_ref', sa.String(1000)),
        sa.Column('extraction_status', sa.String(50), default='pending'),
        sa.Column('extraction_error', sa.Text),

        # Document processing status
        sa.Column('chunk_count', sa.Integer, default=0),
        sa.Column('embedding_status', sa.String(50), default='pending'),

        # Usage mode
        # "retrieval" - used for RAG search
        # "direct" - sent directly to model (images, audio)
        # "both" - used for both
        sa.Column('usage_mode', sa.String(50), default='retrieval'),

        # Audit
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_chat_attachments_conversation_id', 'chat_attachments', ['conversation_id'])
    op.create_index('ix_chat_attachments_message_id', 'chat_attachments', ['message_id'])
    op.create_index('ix_chat_attachments_mime_type', 'chat_attachments', ['mime_type'])
    op.create_index('ix_chat_attachments_extraction_status', 'chat_attachments', ['extraction_status'])

    # =========================================================================
    # chat_doc_chunks - Document chunks for RAG
    # =========================================================================
    op.create_table(
        'chat_doc_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('attachment_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_attachments.id', ondelete='CASCADE'), nullable=False),

        # Chunk identification
        sa.Column('chunk_index', sa.Integer, nullable=False),

        # Content
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('char_count', sa.Integer),
        sa.Column('token_count', sa.Integer),

        # Position in source document
        sa.Column('start_char', sa.Integer),
        sa.Column('end_char', sa.Integer),
        sa.Column('page_number', sa.Integer),  # For PDFs

        # Metadata for citations
        # Format: {"section": "Introduction", "heading": "1.1 Overview"}
        sa.Column('metadata', postgresql.JSONB, default=dict),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_chat_doc_chunks_attachment_id', 'chat_doc_chunks', ['attachment_id'])
    op.create_index('ix_chat_doc_chunks_chunk_index', 'chat_doc_chunks', ['chunk_index'])
    op.create_unique_constraint('uq_chat_doc_chunks_attachment_index',
                                'chat_doc_chunks', ['attachment_id', 'chunk_index'])

    # =========================================================================
    # chat_doc_embeddings - Vector embeddings for document search
    # Using pgvector for vector storage
    # =========================================================================
    # First, ensure pgvector extension is available
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'chat_doc_embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('chunk_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_doc_chunks.id', ondelete='CASCADE'), nullable=False),

        # Embedding vector (1536 dimensions for OpenAI, adjust as needed)
        # Using pgvector's vector type
        sa.Column('embedding', postgresql.ARRAY(sa.Float)),

        # Model used to generate embedding
        sa.Column('model_profile_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_model_profiles.id', ondelete='SET NULL')),
        sa.Column('embedding_model', sa.String(255)),
        sa.Column('embedding_dimensions', sa.Integer),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_chat_doc_embeddings_chunk_id', 'chat_doc_embeddings', ['chunk_id'])
    op.create_index('ix_chat_doc_embeddings_model_profile_id', 'chat_doc_embeddings', ['model_profile_id'])

    # Create vector index for similarity search (using IVFFlat)
    # Note: This requires pgvector extension
    # We'll create this with raw SQL since Alembic doesn't have built-in pgvector support
    # For large datasets, consider using HNSW index instead
    op.execute("""
        DO $$ BEGIN
            -- Convert float array to vector for indexing
            -- Index will be created after data migration if needed
            -- For now, we store as float array and cast during queries
        END $$;
    """)

    # =========================================================================
    # chat_public_apps - Public chat application configurations
    # =========================================================================
    op.create_table(
        'chat_public_apps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Public URL slug - e.g., /public/chat/my-assistant
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(2000)),

        # Welcome message shown to users
        sa.Column('welcome_message', sa.Text),

        # Token for access (hashed)
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('token_prefix', sa.String(12)),  # First 8 chars for identification

        # Allowed model profiles
        sa.Column('allowed_model_profile_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), default=list),

        # Default model profile for new conversations
        sa.Column('default_model_profile_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_model_profiles.id', ondelete='SET NULL')),

        # Feature toggles
        sa.Column('allow_upload', sa.Boolean, default=False, nullable=False),
        sa.Column('allow_web_search', sa.Boolean, default=False, nullable=False),
        sa.Column('allow_doc_search', sa.Boolean, default=True, nullable=False),
        sa.Column('allow_model_selection', sa.Boolean, default=False, nullable=False),

        # Constraints
        sa.Column('max_file_size_mb', sa.Integer, default=10),
        sa.Column('max_files_per_conversation', sa.Integer, default=10),
        sa.Column('max_messages_per_conversation', sa.Integer, default=100),
        sa.Column('max_conversations_per_token', sa.Integer, default=10),

        # Rate limiting
        # Format: {"requests_per_minute": 10, "messages_per_day": 100}
        sa.Column('rate_limit', postgresql.JSONB, default=dict),

        # System prompt override (optional)
        sa.Column('system_prompt', sa.Text),

        # Model parameters override
        sa.Column('model_params', postgresql.JSONB, default=dict),

        # Branding
        sa.Column('logo_url', sa.String(2000)),
        sa.Column('primary_color', sa.String(7)),  # Hex color
        sa.Column('custom_css', sa.Text),

        # Access control
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('enabled', sa.Boolean, default=True, nullable=False),

        # Analytics
        sa.Column('total_conversations', sa.Integer, default=0),
        sa.Column('total_messages', sa.Integer, default=0),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),

        # Audit
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_chat_public_apps_tenant_id', 'chat_public_apps', ['tenant_id'])
    op.create_index('ix_chat_public_apps_enabled', 'chat_public_apps', ['enabled'])
    op.create_unique_constraint('uq_chat_public_apps_slug', 'chat_public_apps', ['slug'])

    # Add foreign key for public_app_id in conversations
    op.create_foreign_key(
        'fk_chat_conversations_public_app',
        'chat_conversations', 'chat_public_apps',
        ['public_app_id'], ['id'],
        ondelete='SET NULL'
    )

    # =========================================================================
    # chat_mcp_servers - MCP server configurations
    # =========================================================================
    op.create_table(
        'chat_mcp_servers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Server identification
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000)),

        # Transport type
        sa.Column('transport', sa.Enum(
            'stdio', 'sse', 'streamable_http',
            name='chat_mcp_transport', create_type=False
        ), nullable=False),

        # Connection configuration based on transport type
        # For stdio: {"command": "python", "args": ["-m", "mcp_server"]}
        # For sse/http: {"url": "http://localhost:8080/mcp"}
        sa.Column('connection_config', postgresql.JSONB, nullable=False),

        # Environment variables for stdio transport
        sa.Column('environment', postgresql.JSONB, default=dict),

        # Server capabilities (discovered or configured)
        # Format: {"tools": true, "prompts": true, "resources": true}
        sa.Column('capabilities', postgresql.JSONB, default=dict),

        # Discovered tools cache
        # Format: [{"name": "search", "description": "...", "inputSchema": {...}}]
        sa.Column('tools_cache', postgresql.JSONB, default=list),
        sa.Column('tools_cache_updated_at', sa.DateTime(timezone=True)),

        # Security settings
        # Allowlist of tools that can be called
        sa.Column('allowed_tools', postgresql.ARRAY(sa.String), default=list),

        # Rate limiting for this server
        sa.Column('rate_limit', postgresql.JSONB, default=dict),

        # Server status
        sa.Column('status', sa.Enum(
            'active', 'inactive', 'error',
            name='chat_mcp_server_status', create_type=False
        ), default='inactive'),
        sa.Column('last_health_check', sa.DateTime(timezone=True)),
        sa.Column('health_check_error', sa.Text),

        # Ordering for tool display
        sa.Column('display_order', sa.Integer, default=100),

        # Status
        sa.Column('enabled', sa.Boolean, default=True, nullable=False),

        # Audit
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_chat_mcp_servers_tenant_id', 'chat_mcp_servers', ['tenant_id'])
    op.create_index('ix_chat_mcp_servers_enabled', 'chat_mcp_servers', ['enabled'])
    op.create_index('ix_chat_mcp_servers_transport', 'chat_mcp_servers', ['transport'])
    op.create_unique_constraint('uq_chat_mcp_servers_tenant_name', 'chat_mcp_servers',
                                ['tenant_id', 'name'])

    # =========================================================================
    # chat_mcp_tool_calls - MCP tool call audit logs
    # =========================================================================
    op.create_table(
        'chat_mcp_tool_calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Context
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_conversations.id', ondelete='SET NULL')),
        sa.Column('message_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_messages.id', ondelete='SET NULL')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL')),

        # MCP server
        sa.Column('mcp_server_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_mcp_servers.id', ondelete='SET NULL')),
        sa.Column('mcp_server_name', sa.String(255)),

        # Tool call details
        sa.Column('tool_name', sa.String(255), nullable=False),
        sa.Column('tool_call_id', sa.String(255)),  # OpenAI-style tool call ID

        # Arguments (potentially redacted for security)
        sa.Column('arguments', postgresql.JSONB),
        sa.Column('arguments_redacted', sa.Boolean, default=False),

        # Result (potentially truncated for large responses)
        sa.Column('result', postgresql.JSONB),
        sa.Column('result_truncated', sa.Boolean, default=False),

        # Status
        sa.Column('status', sa.String(50), nullable=False),  # success, error, timeout
        sa.Column('error_message', sa.Text),

        # Timing
        sa.Column('latency_ms', sa.Integer),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_chat_mcp_tool_calls_tenant_id', 'chat_mcp_tool_calls', ['tenant_id'])
    op.create_index('ix_chat_mcp_tool_calls_conversation_id', 'chat_mcp_tool_calls', ['conversation_id'])
    op.create_index('ix_chat_mcp_tool_calls_user_id', 'chat_mcp_tool_calls', ['user_id'])
    op.create_index('ix_chat_mcp_tool_calls_mcp_server_id', 'chat_mcp_tool_calls', ['mcp_server_id'])
    op.create_index('ix_chat_mcp_tool_calls_tool_name', 'chat_mcp_tool_calls', ['tool_name'])
    op.create_index('ix_chat_mcp_tool_calls_status', 'chat_mcp_tool_calls', ['status'])
    op.create_index('ix_chat_mcp_tool_calls_created_at', 'chat_mcp_tool_calls', ['created_at'])


def downgrade() -> None:
    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_table('chat_mcp_tool_calls')
    op.drop_table('chat_mcp_servers')

    # Remove foreign key before dropping public_apps
    op.drop_constraint('fk_chat_conversations_public_app',
                       'chat_conversations', type_='foreignkey')

    op.drop_table('chat_public_apps')
    op.drop_table('chat_doc_embeddings')
    op.drop_table('chat_doc_chunks')
    op.drop_table('chat_attachments')
    op.drop_table('chat_messages')
    op.drop_table('chat_conversations')
    op.drop_table('chat_model_profiles')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS chat_message_role")
    op.execute("DROP TYPE IF EXISTS chat_mcp_transport")
    op.execute("DROP TYPE IF EXISTS chat_mcp_server_status")
