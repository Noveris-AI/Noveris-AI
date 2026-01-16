"""
AI Gateway Database Models.

This module contains all database models for the AI Gateway / Model Forwarding system:
- GatewaySecret: Encrypted credential storage
- GatewayUpstream: Upstream provider configurations
- GatewayVirtualModel: Exposed model identifiers
- GatewayRoute: Routing policies
- GatewayAPIKey: External API keys
- GatewayRequest: Request logs for observability

Reference documentation:
- Architecture: /Docs/gateway-architecture.md
- OpenAI API: https://platform.openai.com/docs/api-reference
- Helicone: https://docs.helicone.ai/gateway/overview
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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

class UpstreamType(str, enum.Enum):
    """Types of upstream providers."""

    OPENAI = "openai"                     # Official OpenAI API
    OPENAI_COMPATIBLE = "openai_compatible"  # vLLM, sglang, Xinference, etc.
    ANTHROPIC = "anthropic"               # Anthropic Claude
    GEMINI = "gemini"                     # Google Gemini
    COHERE = "cohere"                     # Cohere (embeddings, rerank)
    STABLE_DIFFUSION = "stable_diffusion" # SD WebUI/A1111
    CUSTOM_HTTP = "custom_http"           # Generic HTTP adapter


class AuthType(str, enum.Enum):
    """Authentication types for upstreams."""

    BEARER = "bearer"   # Authorization: Bearer <token>
    HEADER = "header"   # Custom header (configured in credentials)
    QUERY = "query"     # Query parameter (configured in credentials)
    NONE = "none"       # No authentication


class LogPayloadMode(str, enum.Enum):
    """Logging policy for request/response payloads."""

    NONE = "none"                       # No payload logging
    METADATA_ONLY = "metadata_only"     # Only metadata (tokens, latency, etc.)
    SAMPLED = "sampled"                 # Sample % of requests
    FULL_WITH_REDACTION = "full_with_redaction"  # Full payload with sensitive field redaction


class Capability(str, enum.Enum):
    """Supported AI capabilities."""

    CHAT_COMPLETIONS = "chat_completions"
    COMPLETIONS = "completions"
    RESPONSES = "responses"
    EMBEDDINGS = "embeddings"
    IMAGES_GENERATIONS = "images_generations"
    IMAGES_EDITS = "images_edits"
    IMAGES_VARIATIONS = "images_variations"
    AUDIO_SPEECH = "audio_speech"
    AUDIO_TRANSCRIPTIONS = "audio_transcriptions"
    AUDIO_TRANSLATIONS = "audio_translations"
    MODERATIONS = "moderations"
    RERANK = "rerank"


# =============================================================================
# Models
# =============================================================================

class GatewaySecret(Base):
    """
    Encrypted credential storage for upstream providers.

    Credentials are encrypted using Fernet (AES-128-CBC with HMAC).
    The encryption key is stored in environment variable GATEWAY_SECRET_ENCRYPTION_KEY.
    """

    __tablename__ = "gateway_secrets"
    __table_args__ = (
        Index("ix_gateway_secrets_tenant_id", "tenant_id"),
        UniqueConstraint("tenant_id", "name", name="uq_gateway_secrets_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(String(500))

    # Encrypted value (Fernet encrypted, base64 encoded)
    ciphertext = Column(Text, nullable=False)
    key_version = Column(Integer, default=1, nullable=False)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    upstreams = relationship("GatewayUpstream", back_populates="credentials_secret")

    def __repr__(self):
        return f"<GatewaySecret(id={self.id}, name={self.name})>"


class GatewayUpstream(Base):
    """
    Upstream provider configuration.

    An upstream represents a backend AI service that can handle requests.
    It can be:
    - An external service (OpenAI, Anthropic, etc.)
    - An internal deployment (vLLM, sglang, Xinference on managed nodes)
    """

    __tablename__ = "gateway_upstreams"
    __table_args__ = (
        Index("ix_gateway_upstreams_tenant_id", "tenant_id"),
        Index("ix_gateway_upstreams_type", "type"),
        Index("ix_gateway_upstreams_enabled", "enabled"),
        Index("ix_gateway_upstreams_deployment_id", "deployment_id"),
        UniqueConstraint("tenant_id", "name", name="uq_gateway_upstreams_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    # Provider type determines which adapter to use
    type = Column(Enum(UpstreamType), nullable=False)

    # Connection configuration
    base_url = Column(String(2000), nullable=False)
    auth_type = Column(Enum(AuthType), default=AuthType.BEARER)

    # Reference to encrypted credential
    credentials_secret_id = Column(
        UUID(as_uuid=True),
        ForeignKey("gateway_secrets.id", ondelete="SET NULL")
    )

    # Security - SSRF protection
    # Allowlist of hostnames that this upstream can redirect to
    allow_hosts = Column(ARRAY(String), default=list)
    # Allowlist of CIDRs that resolved IPs must match
    allow_cidrs = Column(ARRAY(String), default=list)

    # Capabilities this upstream supports
    supported_capabilities = Column(ARRAY(String), default=list)

    # Model mapping: virtual_model_name -> upstream_model_name
    model_mapping = Column(JSONB, default=dict)

    # Healthcheck configuration
    # Example: {"path": "/health", "method": "GET", "interval_seconds": 30,
    #           "timeout_seconds": 5, "expected_status": 200}
    healthcheck = Column(JSONB, default=dict)

    # Reliability settings
    timeout_ms = Column(Integer, default=120000)  # 2 minutes default
    max_retries = Column(Integer, default=2)

    # Circuit breaker configuration
    # Example: {"failure_threshold": 5, "success_threshold": 3,
    #           "timeout_seconds": 60, "half_open_max_requests": 3}
    circuit_breaker = Column(JSONB, default=dict)

    # Current health status (updated by healthcheck worker)
    health_status = Column(String(20), default="unknown")
    last_health_check_at = Column(DateTime(timezone=True))
    health_check_error = Column(Text)

    # Link to internal deployment (if this upstream is a deployed model)
    deployment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="SET NULL")
    )

    enabled = Column(Boolean, default=True, nullable=False)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    credentials_secret = relationship("GatewaySecret", back_populates="upstreams")
    deployment = relationship("Deployment", backref="gateway_upstreams")
    requests = relationship("GatewayRequest", back_populates="upstream")

    def __repr__(self):
        return f"<GatewayUpstream(id={self.id}, name={self.name}, type={self.type.value})>"


class GatewayVirtualModel(Base):
    """
    Virtual model definition.

    A virtual model is the externally exposed model identifier that clients use.
    It abstracts the actual upstream model and allows for:
    - Model aliasing (e.g., "gpt-4" -> "gpt-4-turbo-preview")
    - Multi-provider routing (same virtual model can route to different upstreams)
    - Capability declaration (what endpoints this model supports)
    """

    __tablename__ = "gateway_virtual_models"
    __table_args__ = (
        Index("ix_gateway_virtual_models_tenant_id", "tenant_id"),
        Index("ix_gateway_virtual_models_enabled", "enabled"),
        UniqueConstraint("tenant_id", "name", name="uq_gateway_virtual_models_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Model identifier (e.g., "openai/gpt-4o", "local/llama3-70b", "embed/bge-m3")
    name = Column(String(500), nullable=False)
    display_name = Column(String(255))
    description = Column(String(1000))

    # Capabilities this virtual model supports
    capabilities = Column(ARRAY(String), default=list)

    # Tags for filtering and routing
    tags = Column(JSONB, default=dict)

    # Default route to use if no specific route matches
    default_route_id = Column(
        UUID(as_uuid=True),
        ForeignKey("gateway_routes.id", ondelete="SET NULL")
    )

    # Model metadata for /v1/models endpoint
    # Example: {"owned_by": "openai", "permission": [...], "created": 1234567890}
    model_metadata = Column(JSONB, default=dict)

    enabled = Column(Boolean, default=True, nullable=False)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    default_route = relationship("GatewayRoute", foreign_keys=[default_route_id])

    def __repr__(self):
        return f"<GatewayVirtualModel(id={self.id}, name={self.name})>"


class GatewayRoute(Base):
    """
    Routing policy definition.

    A route defines how requests are matched and routed to upstreams.
    Routes are evaluated in priority order (lower number = higher priority).
    First matching route wins.
    """

    __tablename__ = "gateway_routes"
    __table_args__ = (
        Index("ix_gateway_routes_tenant_id", "tenant_id"),
        Index("ix_gateway_routes_priority", "priority"),
        Index("ix_gateway_routes_enabled", "enabled"),
        UniqueConstraint("tenant_id", "name", name="uq_gateway_routes_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    # Priority (lower number = higher priority, evaluated first)
    priority = Column(Integer, default=100, nullable=False)

    # Match conditions (all specified conditions must match - AND logic)
    # Example: {
    #   "endpoint": "/v1/chat/completions",
    #   "virtual_model": "openai/*",  // supports wildcards
    #   "tenant_id": "uuid",
    #   "api_key_id": "uuid",
    #   "tags": {"tier": "premium"}
    # }
    match = Column(JSONB, nullable=False, default=dict)

    # Routing action
    # Example: {
    #   "primary_upstreams": [
    #     {"upstream_id": "uuid1", "weight": 70},
    #     {"upstream_id": "uuid2", "weight": 30}
    #   ],
    #   "fallback_upstreams": ["uuid3", "uuid4"],
    #   "retry_policy": {
    #     "max_retries": 2,
    #     "retry_on_status": [500, 502, 503, 504],
    #     "backoff_ms": 1000,
    #     "backoff_multiplier": 2
    #   },
    #   "cache_policy": {
    #     "enabled": true,
    #     "ttl_seconds": 3600
    #   },
    #   "request_transform": {
    #     "inject_headers": {"X-Custom": "value"},
    #     "model_override": "specific-model-name"
    #   },
    #   "timeout_ms_override": 30000
    # }
    action = Column(JSONB, nullable=False, default=dict)

    enabled = Column(Boolean, default=True, nullable=False)

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<GatewayRoute(id={self.id}, name={self.name}, priority={self.priority})>"


class GatewayAPIKey(Base):
    """
    External API key for gateway access.

    API keys are used by external clients to authenticate with the gateway.
    Each key has:
    - Access control (allowed models, endpoints)
    - Rate limiting
    - Quota management
    - Logging policy
    """

    __tablename__ = "gateway_api_keys"
    __table_args__ = (
        Index("ix_gateway_api_keys_tenant_id", "tenant_id"),
        Index("ix_gateway_api_keys_key_prefix", "key_prefix"),
        Index("ix_gateway_api_keys_enabled", "enabled"),
        Index("ix_gateway_api_keys_user_id", "user_id"),
        UniqueConstraint("tenant_id", "name", name="uq_gateway_api_keys_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    # Key storage (bcrypt hash, only prefix shown to users)
    key_prefix = Column(String(12), nullable=False)  # e.g., "sk-abc123"
    key_hash = Column(String(255), nullable=False)   # bcrypt hash

    # Access control
    allowed_models = Column(ARRAY(String), default=list)
    allowed_endpoints = Column(ARRAY(String), default=list)

    # Rate limiting configuration
    rate_limit = Column(JSONB, default=dict)

    # Quota configuration
    quota = Column(JSONB, default=dict)

    # Logging policy
    log_payload_mode = Column(Enum(LogPayloadMode), default=LogPayloadMode.METADATA_ONLY)

    # Optional: link to a user for audit
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    # Expiration
    expires_at = Column(DateTime(timezone=True))

    enabled = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True))

    # Audit
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="gateway_api_keys")
    requests = relationship("GatewayRequest", back_populates="api_key")

    def __repr__(self):
        return f"<GatewayAPIKey(id={self.id}, name={self.name}, prefix={self.key_prefix})>"


class GatewayRequest(Base):
    """
    Gateway request log entry.

    Stores detailed information about each request for:
    - Observability (latency, errors, usage)
    - Auditing (who accessed what)
    - Cost tracking
    - Debugging

    Note: This table will grow large. Consider:
    - Partitioning by created_at (monthly)
    - Cold storage migration (to ClickHouse/S3)
    - TTL-based cleanup
    """

    __tablename__ = "gateway_requests"
    __table_args__ = (
        Index("ix_gateway_requests_tenant_id", "tenant_id"),
        Index("ix_gateway_requests_request_id", "request_id"),
        Index("ix_gateway_requests_trace_id", "trace_id"),
        Index("ix_gateway_requests_api_key_id", "api_key_id"),
        Index("ix_gateway_requests_upstream_id", "upstream_id"),
        Index("ix_gateway_requests_endpoint", "endpoint"),
        Index("ix_gateway_requests_virtual_model", "virtual_model"),
        Index("ix_gateway_requests_status_code", "status_code"),
        Index("ix_gateway_requests_error_type", "error_type"),
        Index("ix_gateway_requests_created_at", "created_at"),
        Index("ix_gateway_requests_tenant_created", "tenant_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Request identification
    request_id = Column(String(64), nullable=False)
    trace_id = Column(String(64))

    # API Key info
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("gateway_api_keys.id", ondelete="SET NULL"))

    # Request info
    endpoint = Column(String(100), nullable=False)
    method = Column(String(10), default="POST")
    virtual_model = Column(String(500))

    # Upstream info
    upstream_id = Column(UUID(as_uuid=True), ForeignKey("gateway_upstreams.id", ondelete="SET NULL"))
    upstream_model = Column(String(500))

    # Response info
    status_code = Column(Integer)
    error_type = Column(String(100))
    error_message = Column(Text)

    # Timing
    latency_ms = Column(Integer)
    upstream_latency_ms = Column(Integer)
    time_to_first_token_ms = Column(Integer)

    # Token usage
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)

    # Cost calculation
    cost_usd = Column(Numeric(precision=12, scale=8))
    estimated_cost = Column(Boolean, default=False)

    # Request/Response metadata (never includes sensitive data)
    request_meta = Column(JSONB, default=dict)
    response_meta = Column(JSONB, default=dict)

    # Optional: sampled request/response body
    request_body_sample = Column(JSONB)
    response_body_sample = Column(JSONB)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    api_key = relationship("GatewayAPIKey", back_populates="requests")
    upstream = relationship("GatewayUpstream", back_populates="requests")

    def __repr__(self):
        return f"<GatewayRequest(id={self.id}, request_id={self.request_id}, endpoint={self.endpoint})>"
