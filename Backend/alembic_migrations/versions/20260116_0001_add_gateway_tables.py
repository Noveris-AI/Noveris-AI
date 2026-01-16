"""Add AI Gateway tables

Revision ID: a1b2c3d4e5f6
Revises: 9b4d6f8e3c2a
Create Date: 2026-01-16 00:01:00.000000

This migration creates tables for the AI Gateway / Model Forwarding module:
- gateway_secrets: Encrypted credential storage
- gateway_upstreams: Upstream provider configurations
- gateway_virtual_models: Exposed model identifiers
- gateway_routes: Routing policies
- gateway_api_keys: External API keys
- gateway_requests: Request logs for observability
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9b4d6f8e3c2a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types using DO blocks to handle partial migration recovery
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE gateway_upstream_type AS ENUM (
                'openai',
                'openai_compatible',
                'anthropic',
                'gemini',
                'cohere',
                'stable_diffusion',
                'custom_http'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE gateway_auth_type AS ENUM (
                'bearer',
                'header',
                'query',
                'none'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE gateway_log_payload_mode AS ENUM (
                'none',
                'metadata_only',
                'sampled',
                'full_with_redaction'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # =========================================================================
    # gateway_secrets - Encrypted credential storage for upstreams
    # =========================================================================
    op.create_table(
        'gateway_secrets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(500)),
        # Encrypted using Fernet (AES-128-CBC with HMAC)
        sa.Column('ciphertext', sa.Text, nullable=False),
        sa.Column('key_version', sa.Integer, default=1, nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_gateway_secrets_tenant_id', 'gateway_secrets', ['tenant_id'])
    op.create_unique_constraint('uq_gateway_secrets_tenant_name', 'gateway_secrets',
                                ['tenant_id', 'name'])

    # =========================================================================
    # gateway_upstreams - Upstream provider configurations
    # =========================================================================
    op.create_table(
        'gateway_upstreams',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000)),

        # Provider type
        sa.Column('type', sa.Enum(
            'openai', 'openai_compatible', 'anthropic', 'gemini',
            'cohere', 'stable_diffusion', 'custom_http',
            name='gateway_upstream_type', create_type=False
        ), nullable=False),

        # Connection
        sa.Column('base_url', sa.String(2000), nullable=False),
        sa.Column('auth_type', sa.Enum(
            'bearer', 'header', 'query', 'none',
            name='gateway_auth_type', create_type=False
        ), default='bearer'),

        # Reference to encrypted credential in gateway_secrets
        sa.Column('credentials_secret_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('gateway_secrets.id', ondelete='SET NULL')),

        # Security - SSRF protection
        # Allowlist of hostnames that this upstream can redirect to
        sa.Column('allow_hosts', postgresql.ARRAY(sa.String), default=list),
        # Allowlist of CIDRs that resolved IPs must match
        sa.Column('allow_cidrs', postgresql.ARRAY(sa.String), default=list),

        # Capabilities this upstream supports
        # Values: chat_completions, completions, responses, embeddings,
        #         images_generations, images_edits, images_variations,
        #         audio_speech, audio_transcriptions, audio_translations,
        #         moderations, rerank
        sa.Column('supported_capabilities', postgresql.ARRAY(sa.String), default=list),

        # Model mapping: virtual_model_name -> upstream_model_name
        # Example: {"gpt-4o": "gpt-4o-2024-08-06", "claude-3": "claude-3-5-sonnet-20241022"}
        sa.Column('model_mapping', postgresql.JSONB, default=dict),

        # Healthcheck configuration
        # Example: {"path": "/health", "method": "GET", "interval_seconds": 30,
        #           "timeout_seconds": 5, "expected_status": 200}
        sa.Column('healthcheck', postgresql.JSONB, default=dict),

        # Reliability settings
        sa.Column('timeout_ms', sa.Integer, default=120000),  # 2 minutes default
        sa.Column('max_retries', sa.Integer, default=2),

        # Circuit breaker configuration
        # Example: {"failure_threshold": 5, "success_threshold": 3,
        #           "timeout_seconds": 60, "half_open_max_requests": 3}
        sa.Column('circuit_breaker', postgresql.JSONB, default=dict),

        # Current health status (updated by healthcheck worker)
        sa.Column('health_status', sa.String(20), default='unknown'),
        sa.Column('last_health_check_at', sa.DateTime(timezone=True)),
        sa.Column('health_check_error', sa.Text),

        # Link to internal deployment (if this upstream is a deployed model)
        sa.Column('deployment_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('deployments.id', ondelete='SET NULL')),

        sa.Column('enabled', sa.Boolean, default=True, nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_gateway_upstreams_tenant_id', 'gateway_upstreams', ['tenant_id'])
    op.create_index('ix_gateway_upstreams_type', 'gateway_upstreams', ['type'])
    op.create_index('ix_gateway_upstreams_enabled', 'gateway_upstreams', ['enabled'])
    op.create_index('ix_gateway_upstreams_deployment_id', 'gateway_upstreams', ['deployment_id'])
    op.create_unique_constraint('uq_gateway_upstreams_tenant_name', 'gateway_upstreams',
                                ['tenant_id', 'name'])

    # =========================================================================
    # gateway_virtual_models - Exposed model identifiers
    # =========================================================================
    op.create_table(
        'gateway_virtual_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Model identifier (e.g., "openai/gpt-4o", "local/llama3-70b", "embed/bge-m3")
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('display_name', sa.String(255)),
        sa.Column('description', sa.String(1000)),

        # Capabilities this virtual model supports
        sa.Column('capabilities', postgresql.ARRAY(sa.String), default=list),

        # Tags for filtering and routing
        sa.Column('tags', postgresql.JSONB, default=dict),

        # Default route to use if no specific route matches
        sa.Column('default_route_id', postgresql.UUID(as_uuid=True)),

        # Model metadata for /v1/models endpoint
        # Example: {"owned_by": "openai", "permission": [...], "created": 1234567890}
        sa.Column('metadata', postgresql.JSONB, default=dict),

        sa.Column('enabled', sa.Boolean, default=True, nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_gateway_virtual_models_tenant_id', 'gateway_virtual_models', ['tenant_id'])
    op.create_index('ix_gateway_virtual_models_enabled', 'gateway_virtual_models', ['enabled'])
    op.create_unique_constraint('uq_gateway_virtual_models_tenant_name', 'gateway_virtual_models',
                                ['tenant_id', 'name'])

    # =========================================================================
    # gateway_routes - Routing policies
    # =========================================================================
    op.create_table(
        'gateway_routes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000)),

        # Priority (lower number = higher priority, evaluated first)
        sa.Column('priority', sa.Integer, default=100, nullable=False),

        # Match conditions (all specified conditions must match - AND logic)
        # Example: {
        #   "endpoint": "/v1/chat/completions",
        #   "virtual_model": "openai/*",  // supports wildcards
        #   "tenant_id": "uuid",
        #   "api_key_id": "uuid",
        #   "tags": {"tier": "premium"}
        # }
        sa.Column('match', postgresql.JSONB, nullable=False, default=dict),

        # Routing action
        # Example: {
        #   "primary_upstreams": [
        #     {"upstream_id": "uuid1", "weight": 70},
        #     {"upstream_id": "uuid2", "weight": 30}
        #   ],
        #   "fallback_upstreams": ["uuid3", "uuid4"],  // ordered fallback chain
        #   "retry_policy": {
        #     "max_retries": 2,
        #     "retry_on_status": [500, 502, 503, 504],
        #     "backoff_ms": 1000,
        #     "backoff_multiplier": 2
        #   },
        #   "cache_policy": {  // only for embeddings/rerank
        #     "enabled": true,
        #     "ttl_seconds": 3600
        #   },
        #   "request_transform": {
        #     "inject_headers": {"X-Custom": "value"},
        #     "model_override": "specific-model-name"
        #   },
        #   "timeout_ms_override": 30000
        # }
        sa.Column('action', postgresql.JSONB, nullable=False, default=dict),

        sa.Column('enabled', sa.Boolean, default=True, nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_gateway_routes_tenant_id', 'gateway_routes', ['tenant_id'])
    op.create_index('ix_gateway_routes_priority', 'gateway_routes', ['priority'])
    op.create_index('ix_gateway_routes_enabled', 'gateway_routes', ['enabled'])
    op.create_unique_constraint('uq_gateway_routes_tenant_name', 'gateway_routes',
                                ['tenant_id', 'name'])

    # Add foreign key for default_route_id after routes table is created
    op.create_foreign_key(
        'fk_gateway_virtual_models_default_route',
        'gateway_virtual_models', 'gateway_routes',
        ['default_route_id'], ['id'],
        ondelete='SET NULL'
    )

    # =========================================================================
    # gateway_api_keys - External API keys for gateway access
    # =========================================================================
    op.create_table(
        'gateway_api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000)),

        # Key storage (bcrypt hash, only prefix shown to users)
        # Format: sk-xxxxxxxx... (prefix stored separately for display)
        sa.Column('key_prefix', sa.String(12), nullable=False),  # e.g., "sk-abc123"
        sa.Column('key_hash', sa.String(255), nullable=False),   # bcrypt hash

        # Access control - which models and endpoints this key can access
        # Empty array means all allowed
        sa.Column('allowed_models', postgresql.ARRAY(sa.String), default=list),
        sa.Column('allowed_endpoints', postgresql.ARRAY(sa.String), default=list),

        # Rate limiting configuration
        # Example: {
        #   "requests_per_minute": 60,
        #   "requests_per_day": 10000,
        #   "tokens_per_minute": 100000,
        #   "tokens_per_day": 1000000
        # }
        sa.Column('rate_limit', postgresql.JSONB, default=dict),

        # Quota configuration
        # Example: {
        #   "max_tokens": 1000000,
        #   "max_requests": 10000,
        #   "reset_interval": "monthly",  // daily, weekly, monthly, never
        #   "current_tokens_used": 0,
        #   "current_requests_used": 0,
        #   "quota_reset_at": "2026-02-01T00:00:00Z"
        # }
        sa.Column('quota', postgresql.JSONB, default=dict),

        # Logging policy for this key
        sa.Column('log_payload_mode', sa.Enum(
            'none', 'metadata_only', 'sampled', 'full_with_redaction',
            name='gateway_log_payload_mode', create_type=False
        ), default='metadata_only'),

        # Optional: link to a user for audit
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL')),

        # Expiration
        sa.Column('expires_at', sa.DateTime(timezone=True)),

        sa.Column('enabled', sa.Boolean, default=True, nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_gateway_api_keys_tenant_id', 'gateway_api_keys', ['tenant_id'])
    op.create_index('ix_gateway_api_keys_key_prefix', 'gateway_api_keys', ['key_prefix'])
    op.create_index('ix_gateway_api_keys_enabled', 'gateway_api_keys', ['enabled'])
    op.create_index('ix_gateway_api_keys_user_id', 'gateway_api_keys', ['user_id'])
    op.create_unique_constraint('uq_gateway_api_keys_tenant_name', 'gateway_api_keys',
                                ['tenant_id', 'name'])

    # =========================================================================
    # gateway_requests - Request logs for observability
    # =========================================================================
    # Note: This table will grow large. Consider:
    # - Partitioning by created_at (monthly)
    # - Cold storage migration (to ClickHouse/S3)
    # - TTL-based cleanup
    op.create_table(
        'gateway_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Request identification
        sa.Column('request_id', sa.String(64), nullable=False),  # Unique per request
        sa.Column('trace_id', sa.String(64)),  # For distributed tracing

        # API Key info
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('gateway_api_keys.id', ondelete='SET NULL')),

        # Request info
        sa.Column('endpoint', sa.String(100), nullable=False),
        sa.Column('method', sa.String(10), default='POST'),
        sa.Column('virtual_model', sa.String(500)),

        # Upstream info
        sa.Column('upstream_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('gateway_upstreams.id', ondelete='SET NULL')),
        sa.Column('upstream_model', sa.String(500)),

        # Response info
        sa.Column('status_code', sa.Integer),
        sa.Column('error_type', sa.String(100)),  # e.g., "rate_limit_exceeded", "upstream_error"
        sa.Column('error_message', sa.Text),

        # Timing
        sa.Column('latency_ms', sa.Integer),  # Total latency
        sa.Column('upstream_latency_ms', sa.Integer),  # Time spent waiting for upstream
        sa.Column('time_to_first_token_ms', sa.Integer),  # For streaming

        # Token usage (if available)
        sa.Column('prompt_tokens', sa.Integer),
        sa.Column('completion_tokens', sa.Integer),
        sa.Column('total_tokens', sa.Integer),

        # Cost calculation
        sa.Column('cost_usd', sa.Numeric(precision=12, scale=8)),
        sa.Column('estimated_cost', sa.Boolean, default=False),  # True if cost is estimated

        # Request/Response metadata (never includes sensitive data)
        # Example request_meta: {
        #   "client_ip": "1.2.3.4",
        #   "user_agent": "...",
        #   "content_length": 1234,
        #   "stream": true
        # }
        sa.Column('request_meta', postgresql.JSONB, default=dict),

        # Example response_meta: {
        #   "finish_reason": "stop",
        #   "model": "gpt-4o-2024-08-06",
        #   "system_fingerprint": "..."
        # }
        sa.Column('response_meta', postgresql.JSONB, default=dict),

        # Optional: sampled request/response body (based on log_payload_mode)
        # Stored with redaction of sensitive fields
        sa.Column('request_body_sample', postgresql.JSONB),
        sa.Column('response_body_sample', postgresql.JSONB),

        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_gateway_requests_tenant_id', 'gateway_requests', ['tenant_id'])
    op.create_index('ix_gateway_requests_request_id', 'gateway_requests', ['request_id'])
    op.create_index('ix_gateway_requests_trace_id', 'gateway_requests', ['trace_id'])
    op.create_index('ix_gateway_requests_api_key_id', 'gateway_requests', ['api_key_id'])
    op.create_index('ix_gateway_requests_upstream_id', 'gateway_requests', ['upstream_id'])
    op.create_index('ix_gateway_requests_endpoint', 'gateway_requests', ['endpoint'])
    op.create_index('ix_gateway_requests_virtual_model', 'gateway_requests', ['virtual_model'])
    op.create_index('ix_gateway_requests_status_code', 'gateway_requests', ['status_code'])
    op.create_index('ix_gateway_requests_error_type', 'gateway_requests', ['error_type'])
    op.create_index('ix_gateway_requests_created_at', 'gateway_requests', ['created_at'])

    # Composite index for common queries
    op.create_index('ix_gateway_requests_tenant_created',
                    'gateway_requests', ['tenant_id', 'created_at'])


def downgrade() -> None:
    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_table('gateway_requests')
    op.drop_table('gateway_api_keys')

    # Remove foreign key before dropping routes
    op.drop_constraint('fk_gateway_virtual_models_default_route',
                       'gateway_virtual_models', type_='foreignkey')

    op.drop_table('gateway_routes')
    op.drop_table('gateway_virtual_models')
    op.drop_table('gateway_upstreams')
    op.drop_table('gateway_secrets')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS gateway_upstream_type")
    op.execute("DROP TYPE IF EXISTS gateway_auth_type")
    op.execute("DROP TYPE IF EXISTS gateway_log_payload_mode")
