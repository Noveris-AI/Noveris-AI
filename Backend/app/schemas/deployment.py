"""
Model Deployment API Schemas.

Pydantic schemas for request/response validation in the Model Deployment API.
Follows strict validation and security practices.

Reference documentation:
- vLLM: https://docs.vllm.ai/en/latest/getting_started/quickstart/
- SGLang: https://docs.sglang.io/
- Xinference: https://inference.readthedocs.io/en/latest/getting_started/using_xinference.html
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Shared/Common Schemas
# =============================================================================

class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(1, ge=1, description="Page number (1-based)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""

    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")

    @classmethod
    def create(cls, total: int, page: int, page_size: int) -> "PaginatedResponse":
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(total=total, page=page, page_size=page_size, total_pages=total_pages)


# =============================================================================
# Environment Variable Table Schemas
# =============================================================================

class EnvTableEntry(BaseModel):
    """Single environment variable entry."""

    name: str = Field(..., min_length=1, max_length=255, description="Environment variable name")
    value: str = Field("", max_length=4096, description="Value (empty if sensitive)")
    is_sensitive: bool = Field(False, description="Whether the value is sensitive (masked)")

    @field_validator("name")
    @classmethod
    def validate_env_name(cls, v: str) -> str:
        """Validate environment variable name follows conventions."""
        v = v.strip()
        if not v:
            raise ValueError("Environment variable name cannot be empty")
        # Allow standard env var naming: letters, numbers, underscore, starting with letter or underscore
        import re
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", v):
            raise ValueError("Invalid environment variable name format")
        return v


# =============================================================================
# CLI Arguments Table Schemas
# =============================================================================

class ArgsTableEntry(BaseModel):
    """Single CLI argument entry."""

    key: str = Field(..., min_length=1, max_length=255, description="Argument key (e.g., --max-model-len)")
    value: str = Field("", max_length=4096, description="Argument value")
    arg_type: str = Field("string", pattern="^(string|int|float|bool|json)$", description="Value type")
    enabled: bool = Field(True, description="Whether this argument is enabled")

    @field_validator("key")
    @classmethod
    def validate_arg_key(cls, v: str) -> str:
        """Validate argument key format."""
        v = v.strip()
        if not v:
            raise ValueError("Argument key cannot be empty")
        # Allow standard CLI argument naming: starts with - or --
        if not v.startswith("-"):
            v = f"--{v}"
        return v


# =============================================================================
# Deployment Schemas
# =============================================================================

class DeploymentBase(BaseModel):
    """Base deployment schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique deployment name")
    display_name: Optional[str] = Field(None, max_length=255, description="Human-readable display name")
    description: Optional[str] = Field(None, max_length=2000, description="Deployment description")
    framework: str = Field(..., pattern="^(vllm|sglang|xinference)$", description="Serving framework")
    deployment_mode: str = Field("native", pattern="^(native|docker)$", description="Deployment mode")


class DeploymentCreate(DeploymentBase):
    """Schema for creating a new deployment."""

    # Node selection
    node_id: uuid.UUID = Field(..., description="Target node ID")

    # Model source
    model_source: str = Field("huggingface", pattern="^(huggingface|modelscope|local)$")
    model_repo_id: str = Field(..., min_length=1, max_length=500, description="Model repository ID (e.g., meta-llama/Llama-2-7b-chat-hf)")
    model_revision: Optional[str] = Field(None, max_length=100, description="Model revision/branch/tag")

    # Service configuration
    host: str = Field("0.0.0.0", max_length=255, description="Bind host")
    port: Optional[int] = Field(None, ge=1024, le=65535, description="Service port (auto-allocated if not specified)")
    served_model_name: Optional[str] = Field(None, max_length=255, description="Name to expose via API")

    # GPU configuration
    gpu_devices: Optional[List[int]] = Field(None, description="GPU device indices to use")
    tensor_parallel_size: int = Field(1, ge=1, le=32, description="Tensor parallelism degree")
    gpu_memory_utilization: float = Field(0.9, ge=0.1, le=1.0, description="GPU memory utilization ratio")

    # Environment variables (non-sensitive stored directly, sensitive values provided separately)
    env_table: List[EnvTableEntry] = Field(default_factory=list, description="Environment variables")

    # CLI arguments
    args_table: List[ArgsTableEntry] = Field(default_factory=list, description="CLI arguments")

    # Labels and tags
    labels: Dict[str, str] = Field(default_factory=dict, description="Labels for filtering")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")

    @field_validator("model_repo_id")
    @classmethod
    def validate_model_repo_id(cls, v: str) -> str:
        """Validate model repository ID format."""
        v = v.strip()
        if not v:
            raise ValueError("Model repository ID cannot be empty")
        # Basic validation - should contain org/model format for HF
        if "/" not in v and not v.startswith("/"):
            raise ValueError("Model repository ID should be in format 'org/model' or absolute path")
        return v

    @model_validator(mode="after")
    def validate_gpu_config(self):
        """Validate GPU configuration is consistent."""
        if self.gpu_devices:
            # Ensure tensor_parallel_size doesn't exceed available devices
            if self.tensor_parallel_size > len(self.gpu_devices):
                raise ValueError(f"tensor_parallel_size ({self.tensor_parallel_size}) cannot exceed number of GPU devices ({len(self.gpu_devices)})")
        return self


class DeploymentUpdate(BaseModel):
    """Schema for updating a deployment."""

    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)

    # GPU configuration (requires restart)
    gpu_devices: Optional[List[int]] = Field(None)
    tensor_parallel_size: Optional[int] = Field(None, ge=1, le=32)
    gpu_memory_utilization: Optional[float] = Field(None, ge=0.1, le=1.0)

    # Environment and arguments (requires restart)
    env_table: Optional[List[EnvTableEntry]] = None
    args_table: Optional[List[ArgsTableEntry]] = None

    # Labels and tags
    labels: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None


class DeploymentResponse(DeploymentBase):
    """Schema for deployment response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    node_id: Optional[uuid.UUID]

    # Model info
    model_source: str
    model_repo_id: str
    model_revision: Optional[str]
    model_local_path: Optional[str]

    # Service config
    host: str
    port: int
    served_model_name: Optional[str]

    # GPU config
    gpu_devices: Optional[List[int]]
    tensor_parallel_size: int
    gpu_memory_utilization: float

    # Environment and args (sensitive values masked)
    env_table: List[EnvTableEntry]
    args_table: List[ArgsTableEntry]

    # Status
    status: str
    health_status: str
    last_health_check_at: Optional[datetime]
    error_message: Optional[str]

    # Endpoints
    endpoints: Dict[str, str]

    # Labels and tags
    labels: Dict[str, str]
    tags: List[str]

    # Audit
    created_by: uuid.UUID
    created_by_email: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    stopped_at: Optional[datetime]

    # Node info (joined)
    node_name: Optional[str] = None
    node_host: Optional[str] = None


class DeploymentListResponse(BaseModel):
    """Schema for paginated deployment list response."""

    deployments: List[DeploymentResponse]
    pagination: PaginatedResponse


class DeploymentDetailResponse(DeploymentResponse):
    """Extended schema for deployment detail."""

    # Systemd service info
    systemd_service_name: Optional[str]
    systemd_unit_path: Optional[str]
    wrapper_script_path: Optional[str]
    config_json_path: Optional[str]
    log_dir: Optional[str]

    # Job tracking
    install_job_run_id: Optional[uuid.UUID]
    start_job_run_id: Optional[uuid.UUID]
    stop_job_run_id: Optional[uuid.UUID]

    # Error detail
    error_detail: Optional[str]
    retry_count: int
    max_retries: int

    # Recent logs
    recent_logs: List["DeploymentLogResponse"] = Field(default_factory=list)


# =============================================================================
# Deployment Log Schemas
# =============================================================================

class DeploymentLogResponse(BaseModel):
    """Schema for deployment log entry response."""

    id: uuid.UUID
    deployment_id: uuid.UUID
    level: str
    message: str
    source: Optional[str]
    operation: Optional[str]
    job_run_id: Optional[uuid.UUID]
    data: Optional[Dict[str, Any]]
    created_at: datetime


class DeploymentLogListResponse(BaseModel):
    """Schema for paginated deployment log list response."""

    logs: List[DeploymentLogResponse]
    pagination: PaginatedResponse


# =============================================================================
# Compatibility Schemas
# =============================================================================

class CompatibilityCheckRequest(BaseModel):
    """Schema for compatibility check request."""

    node_id: uuid.UUID = Field(..., description="Node to check compatibility for")
    frameworks: Optional[List[str]] = Field(
        None,
        description="Frameworks to check (defaults to all: vllm, sglang, xinference)"
    )


class FrameworkCompatibility(BaseModel):
    """Compatibility result for a single framework."""

    framework: str
    supported: bool
    reason: Optional[str] = None
    install_profile: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, str]] = None


class CompatibilityCheckResponse(BaseModel):
    """Schema for compatibility check response."""

    node_id: uuid.UUID
    node_name: str
    node_host: str
    frameworks: List[FrameworkCompatibility]
    evaluated_at: datetime


# =============================================================================
# Action Schemas
# =============================================================================

class DeploymentActionResponse(BaseModel):
    """Schema for deployment action response (start/stop/restart)."""

    deployment_id: uuid.UUID
    action: str
    status: str
    job_run_id: Optional[uuid.UUID] = None
    message: str


class DeploymentHealthResponse(BaseModel):
    """Schema for deployment health check response."""

    deployment_id: uuid.UUID
    health_status: str
    last_check_at: datetime
    endpoints: Dict[str, str]
    error: Optional[str] = None
    response_time_ms: Optional[float] = None


# =============================================================================
# Service Log Streaming Schemas
# =============================================================================

class LogStreamRequest(BaseModel):
    """Schema for log stream request parameters."""

    lines: int = Field(100, ge=1, le=10000, description="Number of lines to return")
    follow: bool = Field(False, description="Whether to follow logs (streaming)")
    source: str = Field("all", pattern="^(stdout|stderr|all)$", description="Log source")


class LogLine(BaseModel):
    """Single log line."""

    timestamp: Optional[datetime]
    source: str
    content: str


class LogStreamResponse(BaseModel):
    """Schema for log stream response."""

    deployment_id: uuid.UUID
    lines: List[LogLine]
    has_more: bool


# =============================================================================
# Port Allocation Schemas
# =============================================================================

class PortAllocationResponse(BaseModel):
    """Schema for port allocation response."""

    id: uuid.UUID
    node_id: uuid.UUID
    port: int
    deployment_id: Optional[uuid.UUID]
    is_active: bool
    allocated_at: datetime
    released_at: Optional[datetime]


# =============================================================================
# GPU/Accelerator Selection Schemas
# =============================================================================

class AcceleratorDevice(BaseModel):
    """Single accelerator device info for selection."""

    index: int
    device_type: str
    vendor: str
    model: str
    memory_mb: int
    uuid: Optional[str] = None
    health_status: str = "unknown"
    utilization_percent: Optional[int] = None


class NodeAcceleratorsResponse(BaseModel):
    """Schema for node accelerators response (for GPU selection UI)."""

    node_id: uuid.UUID
    node_name: str
    accelerator_type: Optional[str]
    accelerator_count: int
    devices: List[AcceleratorDevice]


# =============================================================================
# Quick Deploy Schemas (for simplified deployment)
# =============================================================================

class QuickDeployRequest(BaseModel):
    """Schema for quick deployment (minimal configuration)."""

    name: str = Field(..., min_length=1, max_length=255)
    node_id: uuid.UUID
    model_repo_id: str = Field(..., min_length=1, max_length=500)
    framework: str = Field("vllm", pattern="^(vllm|sglang|xinference)$")

    # Optional overrides
    port: Optional[int] = Field(None, ge=1024, le=65535)
    gpu_devices: Optional[List[int]] = None


class QuickDeployResponse(BaseModel):
    """Schema for quick deployment response."""

    deployment_id: uuid.UUID
    status: str
    message: str
    estimated_time_minutes: Optional[int] = None


# =============================================================================
# Framework Configuration Templates
# =============================================================================

class FrameworkConfigTemplate(BaseModel):
    """Framework-specific configuration template."""

    framework: str
    description: str
    recommended_args: List[ArgsTableEntry]
    recommended_env: List[EnvTableEntry]
    documentation_url: str


class FrameworkConfigTemplatesResponse(BaseModel):
    """Schema for framework configuration templates response."""

    templates: List[FrameworkConfigTemplate]


# Update forward references
DeploymentDetailResponse.model_rebuild()
