"""
Model Deployment Database Models.

This module contains all database models for the Model Deployment system including:
- Deployments (model serving instances)
- Deployment Logs (execution logs)
- Port Allocations (tracking used ports)
- Secrets KV (encrypted sensitive values)

Reference documentation:
- vLLM: https://docs.vllm.ai/en/latest/getting_started/quickstart/
- SGLang: https://docs.sglang.io/
- Xinference: https://inference.readthedocs.io/en/latest/getting_started/using_xinference.html
"""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    ARRAY,
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


class DeploymentFramework(str, enum.Enum):
    """Supported model serving frameworks."""

    VLLM = "vllm"
    SGLANG = "sglang"
    XINFERENCE = "xinference"


class DeploymentStatus(str, enum.Enum):
    """Deployment lifecycle status."""

    PENDING = "PENDING"           # Waiting for resources
    DOWNLOADING = "DOWNLOADING"   # Model download in progress
    INSTALLING = "INSTALLING"     # Framework installation in progress
    STARTING = "STARTING"         # Service starting up
    RUNNING = "RUNNING"           # Service is running and healthy
    STOPPED = "STOPPED"           # Service stopped
    FAILED = "FAILED"             # Deployment failed
    DELETING = "DELETING"         # Cleanup in progress


class DeploymentMode(str, enum.Enum):
    """Deployment execution mode."""

    NATIVE = "native"      # Native SDK/CLI with systemd
    DOCKER = "docker"      # Docker container (if available)


class ModelSource(str, enum.Enum):
    """Model source types."""

    HUGGINGFACE = "huggingface"
    MODELSCOPE = "modelscope"
    LOCAL = "local"


class Deployment(Base):
    """
    Model Deployment instance.

    Represents a deployed model service on a managed node.
    Supports vLLM, SGLang, and Xinference frameworks with
    OpenAI-compatible API endpoints.
    """

    __tablename__ = "deployments"
    __table_args__ = (
        Index("ix_deployments_tenant_id", "tenant_id"),
        Index("ix_deployments_node_id", "node_id"),
        Index("ix_deployments_status", "status"),
        Index("ix_deployments_framework", "framework"),
        UniqueConstraint("tenant_id", "name", name="uq_deployment_tenant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Basic identification
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)

    # Framework configuration
    framework = Column(Enum(DeploymentFramework, create_type=False), nullable=False)
    deployment_mode = Column(Enum(DeploymentMode, create_type=False), default=DeploymentMode.NATIVE)

    # Node assignment
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True)

    # Model source configuration
    model_source = Column(Enum(ModelSource, create_type=False), default=ModelSource.HUGGINGFACE)
    model_repo_id = Column(String(500), nullable=False)  # e.g., "meta-llama/Llama-2-7b-chat-hf"
    model_revision = Column(String(100))  # Git revision/tag
    model_local_path = Column(String(1000))  # Path on target node after download

    # Service configuration
    host = Column(String(255), default="0.0.0.0")
    port = Column(Integer, nullable=False)
    served_model_name = Column(String(255))  # Name exposed via API

    # GPU/Accelerator configuration
    gpu_devices = Column(ARRAY(Integer))  # Device indices [0, 1, 2, ...]
    tensor_parallel_size = Column(Integer, default=1)
    gpu_memory_utilization = Column(Float, default=0.9)

    # Environment variables table (non-sensitive values stored directly)
    # Format: [{"name": "KEY", "value": "val", "is_sensitive": false}, ...]
    env_table = Column(JSONB, default=list)

    # CLI arguments table
    # Format: [{"key": "--max-model-len", "value": "4096", "type": "int", "enabled": true}, ...]
    args_table = Column(JSONB, default=list)

    # Sensitive environment variable references (actual values in secrets_kv)
    # Format: {"HF_TOKEN": "secret_uuid_1", "API_KEY": "secret_uuid_2"}
    sensitive_env_refs = Column(JSONB, default=dict)

    # Status and health
    status = Column(Enum(DeploymentStatus, create_type=False), default=DeploymentStatus.PENDING, nullable=False)
    health_status = Column(String(50), default="unknown")  # healthy, unhealthy, unknown
    last_health_check_at = Column(DateTime(timezone=True))
    health_check_error = Column(Text)

    # Endpoints (populated after successful deployment)
    # Format: {"openai_base_url": "http://...", "metrics_url": "http://...", "health_url": "..."}
    endpoints = Column(JSONB, default=dict)

    # Systemd service info
    systemd_service_name = Column(String(255))
    systemd_unit_path = Column(String(500))
    wrapper_script_path = Column(String(500))
    config_json_path = Column(String(500))
    pid_file_path = Column(String(500))

    # Log configuration
    log_dir = Column(String(500))
    stdout_log_path = Column(String(500))
    stderr_log_path = Column(String(500))

    # Ansible job tracking
    install_job_run_id = Column(UUID(as_uuid=True))
    start_job_run_id = Column(UUID(as_uuid=True))
    stop_job_run_id = Column(UUID(as_uuid=True))
    uninstall_job_run_id = Column(UUID(as_uuid=True))

    # Error tracking
    error_message = Column(Text)
    error_detail = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Metadata
    labels = Column(JSONB, default=dict)
    tags = Column(ARRAY(String), default=list)

    # Audit
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_by_email = Column(String(255))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True))
    stopped_at = Column(DateTime(timezone=True))

    # Relationships
    node = relationship("Node", backref="deployments")
    logs = relationship("DeploymentLog", back_populates="deployment", cascade="all, delete-orphan", order_by="DeploymentLog.created_at.desc()")

    def __repr__(self):
        return f"<Deployment(id={self.id}, name={self.name}, framework={self.framework.value}, status={self.status.value})>"


class DeploymentLog(Base):
    """
    Deployment operation logs.

    Stores logs from deployment operations (install, start, stop, etc.)
    for debugging and audit purposes.
    """

    __tablename__ = "deployment_logs"
    __table_args__ = (
        Index("ix_deployment_logs_deployment_id", "deployment_id"),
        Index("ix_deployment_logs_created_at", "created_at"),
        Index("ix_deployment_logs_level", "level"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False)

    # Log entry
    level = Column(String(20), default="info")  # debug, info, warning, error
    message = Column(Text, nullable=False)
    source = Column(String(100))  # ansible, systemd, healthcheck, etc.

    # Context
    operation = Column(String(50))  # install, start, stop, healthcheck, etc.
    job_run_id = Column(UUID(as_uuid=True))  # Associated Ansible job if any

    # Extra data
    data = Column(JSONB)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    deployment = relationship("Deployment", back_populates="logs")

    def __repr__(self):
        return f"<DeploymentLog(id={self.id}, deployment_id={self.deployment_id}, level={self.level})>"


class PortAllocation(Base):
    """
    Port allocation tracking.

    Tracks allocated ports across nodes to prevent conflicts.
    Ports are allocated from the configured range (DEPLOY_PORT_RANGE_START to DEPLOY_PORT_RANGE_END).
    """

    __tablename__ = "port_allocations"
    __table_args__ = (
        Index("ix_port_allocations_tenant_id", "tenant_id"),
        Index("ix_port_allocations_node_id", "node_id"),
        UniqueConstraint("node_id", "port", name="uq_port_allocation_node_port"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)

    port = Column(Integer, nullable=False)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    allocated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    released_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<PortAllocation(id={self.id}, node_id={self.node_id}, port={self.port})>"


class SecretsKV(Base):
    """
    Encrypted secrets key-value store.

    Stores sensitive values (API keys, tokens, passwords) encrypted at rest.
    Referenced by deployment.sensitive_env_refs.
    """

    __tablename__ = "secrets_kv"
    __table_args__ = (
        Index("ix_secrets_kv_tenant_id", "tenant_id"),
        UniqueConstraint("tenant_id", "key", name="uq_secrets_kv_tenant_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Key identifier (human readable, e.g., "deployment_xxx_HF_TOKEN")
    key = Column(String(500), nullable=False)

    # Encrypted value (AES-GCM encrypted, base64 encoded)
    ciphertext = Column(Text, nullable=False)
    key_version = Column(Integer, default=1)

    # Metadata
    description = Column(String(500))
    created_by = Column(UUID(as_uuid=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<SecretsKV(id={self.id}, key={self.key})>"


class DeploymentCompatibility(Base):
    """
    Cached deployment compatibility matrix.

    Stores pre-computed compatibility results between nodes and frameworks
    to speed up deployment creation UI.
    """

    __tablename__ = "deployment_compatibility"
    __table_args__ = (
        Index("ix_deployment_compatibility_node_id", "node_id"),
        UniqueConstraint("node_id", "framework", name="uq_deployment_compatibility_node_framework"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)

    framework = Column(Enum(DeploymentFramework), nullable=False)

    # Compatibility result
    supported = Column(Boolean, nullable=False)
    reason = Column(Text)  # Human-readable reason if not supported

    # Recommended installation profile
    # Values: nvidia_cuda, amd_rocm, ascend_cann, cpu_only, apple_mlx, unknown_custom
    install_profile = Column(String(50))

    # Detected capabilities
    # Format: {"cuda_version": "12.4", "rocm_version": null, "python_version": "3.11", ...}
    capabilities = Column(JSONB)

    # Requirements
    # Format: {"cuda": ">=11.8", "python": ">=3.10,<3.13", ...}
    requirements = Column(JSONB)

    # Last evaluation
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<DeploymentCompatibility(node_id={self.node_id}, framework={self.framework.value}, supported={self.supported})>"
