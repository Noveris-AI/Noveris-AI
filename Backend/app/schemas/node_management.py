"""
Node Management API Schemas.

Pydantic schemas for request/response validation in the Node Management API.
Follows strict validation and security practices.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

# =============================================================================
# Shared/Common Schemas
# =============================================================================

class TenantAwareRequest(BaseModel):
    """Base class for requests that include tenant context."""

    tenant_id: uuid.UUID = Field(..., description="Tenant ID for multi-tenancy")


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
        total_pages = (total + page_size - 1) // page_size
        return cls(total=total, page=page, page_size=page_size, total_pages=total_pages)


# =============================================================================
# Node Schemas
# =============================================================================

class NodeBase(BaseModel):
    """Base node schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique node name")
    display_name: Optional[str] = Field(None, max_length=255, description="Human-readable display name")
    host: str = Field(..., min_length=1, max_length=255, description="IP address or hostname")
    port: int = Field(22, ge=1, le=65535, description="SSH port (or WinRM port for Windows)")
    connection_type: str = Field("ssh", pattern="^(ssh|local|winrm)$")
    ssh_user: Optional[str] = Field(None, max_length=100, description="SSH/WinRM username")
    node_type: str = Field("generic", pattern="^(management|compute|login|storage|kube_node|kube_master|slurm_node|slurm_ctrl|edge|windows|generic)$")
    labels: Dict[str, str] = Field(default_factory=dict, description="Flexible labels for scheduling")
    tags: List[str] = Field(default_factory=list, description="Simple tags for filtering")


class NodeCreate(NodeBase):
    """Schema for creating a new node."""

    credential_type: str = Field("ssh_key", pattern="^(ssh_key|password|winrm)$")
    # SSH Credential payload (will be encrypted)
    ssh_private_key: Optional[str] = Field(None, description="SSH private key (PEM format)")
    ssh_key_passphrase: Optional[str] = Field(None, max_length=255, description="Passphrase for private key")
    password: Optional[str] = Field(None, min_length=1, max_length=255, description="Password authentication")

    # WinRM specific fields
    winrm_transport: str = Field("ntlm", pattern="^(ntlm|kerberos|basic|certificate|credssp)$",
                                  description="WinRM authentication transport")
    winrm_cert_pem: Optional[str] = Field(None, description="Client certificate for cert auth")
    winrm_cert_key_pem: Optional[str] = Field(None, description="Client certificate key")
    winrm_server_cert_validation: str = Field("validate", pattern="^(validate|ignore)$",
                                               description="Server certificate validation mode")
    winrm_kerberos_realm: Optional[str] = Field(None, max_length=255, description="Kerberos realm for auth")

    # Group assignments
    group_ids: List[uuid.UUID] = Field(default_factory=list, description="Node groups to join")

    # Optional bastion configuration (SSH jump host)
    bastion_host: Optional[str] = Field(None, max_length=255)
    bastion_user: Optional[str] = Field(None, max_length=100)
    bastion_port: int = Field(22, ge=1, le=65535)
    bastion_credential_type: str = Field("ssh_key", pattern="^(ssh_key|password)$")
    bastion_ssh_key: Optional[str] = Field(None)
    bastion_password: Optional[str] = Field(None)

    @field_validator("ssh_private_key")
    @classmethod
    def validate_ssh_key(cls, v: Optional[str], info) -> Optional[str]:
        if v and not v.strip():
            return None
        # Basic SSH key validation
        if v:
            v = v.strip()
            if not (v.startswith("-----BEGIN") or "PRIVATE KEY" in v):
                raise ValueError("Invalid SSH private key format")
        return v

    @field_validator("port")
    @classmethod
    def validate_port_for_connection_type(cls, v: int, info) -> int:
        # This is called before model_validator, so we can't access connection_type yet
        return v

    @model_validator(mode="after")
    def validate_credentials(self):
        """Ensure valid credentials are provided based on connection type."""
        # Local connections don't need credentials
        if self.connection_type == "local":
            return self

        # WinRM connections
        if self.connection_type == "winrm":
            # Default WinRM ports
            if self.port == 22:  # Default SSH port, switch to WinRM
                self.port = 5986 if self.winrm_server_cert_validation == "validate" else 5985

            # WinRM requires password or certificate
            if self.winrm_transport in ["ntlm", "kerberos", "basic", "credssp"]:
                if not self.password:
                    raise ValueError("password is required for WinRM with NTLM/Kerberos/Basic/CredSSP")
            elif self.winrm_transport == "certificate":
                if not self.winrm_cert_pem or not self.winrm_cert_key_pem:
                    raise ValueError("winrm_cert_pem and winrm_cert_key_pem required for certificate auth")

            # Kerberos requires realm
            if self.winrm_transport == "kerberos" and not self.winrm_kerberos_realm:
                raise ValueError("winrm_kerberos_realm required for Kerberos authentication")

            return self

        # SSH connections
        if self.credential_type == "ssh_key" and not self.ssh_private_key:
            raise ValueError("ssh_private_key is required when credential_type is ssh_key")
        if self.credential_type == "password" and not self.password:
            raise ValueError("password is required when credential_type is password")
        return self


class NodeUpdate(BaseModel):
    """Schema for updating a node."""

    display_name: Optional[str] = Field(None, max_length=255)
    port: Optional[int] = Field(None, ge=1, le=65535)
    ssh_user: Optional[str] = Field(None, max_length=100)
    node_type: Optional[str] = Field(None, pattern="^(management|compute|login|storage|kube_node|kube_master|slurm_node|slurm_ctrl|edge|generic)$")
    labels: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = Field(None, pattern="^(NEW|READY|UNREACHABLE|MAINTENANCE|DECOMMISSIONED)$")
    group_ids: Optional[List[uuid.UUID]] = None


class NodeResponse(NodeBase):
    """Schema for node response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    status: str
    os_release: Optional[str] = None
    kernel_version: Optional[str] = None
    cpu_cores: Optional[int] = None
    cpu_model: Optional[str] = None
    mem_mb: Optional[int] = None
    disk_mb: Optional[int] = None
    architecture: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    last_job_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Relationships (simplified)
    group_ids: List[uuid.UUID] = Field(default_factory=list)
    group_names: List[str] = Field(default_factory=list)

    # Accelerator summary
    accelerator_summary: Dict[str, Any] = Field(default_factory=dict)


class NodeListResponse(BaseModel):
    """Schema for paginated node list response."""

    nodes: List[NodeResponse]
    pagination: PaginatedResponse


class NodeDetailResponse(NodeResponse):
    """Extended schema for node detail with accelerators."""

    credentials_exist: bool  # Don't expose credentials
    bmc_configured: bool
    accelerators: List["AcceleratorResponse"] = Field(default_factory=list)
    last_facts: Optional[Dict[str, Any]] = None


# =============================================================================
# Credential Schemas
# =============================================================================

class CredentialUpdate(BaseModel):
    """Schema for updating node credentials."""

    credential_type: str = Field(..., pattern="^(ssh_key|password)$")
    ssh_private_key: Optional[str] = Field(None, description="New SSH private key")
    ssh_key_passphrase: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=255)
    bastion_host: Optional[str] = Field(None, max_length=255)
    bastion_user: Optional[str] = Field(None, max_length=100)
    bastion_port: int = Field(22, ge=1, le=65535)
    bastion_credential_type: str = Field("ssh_key", pattern="^(ssh_key|password)$")
    bastion_ssh_key: Optional[str] = Field(None)
    bastion_password: Optional[str] = Field(None)


class BmcCredentialCreate(BaseModel):
    """Schema for creating BMC credentials."""

    bmc_host: str = Field(..., min_length=1, max_length=255)
    bmc_port: int = Field(443, ge=1, le=65535)
    bmc_protocol: str = Field("redfish", pattern="^(redfish|ipmi)$")
    bmc_user: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=255)


class BmcCredentialUpdate(BaseModel):
    """Schema for updating BMC credentials."""

    bmc_host: Optional[str] = Field(None, min_length=1, max_length=255)
    bmc_port: Optional[int] = Field(None, ge=1, le=65535)
    bmc_protocol: Optional[str] = Field(None, pattern="^(redfish|ipmi)$")
    bmc_user: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=8, max_length=255)


class BmcCredentialResponse(BaseModel):
    """Schema for BMC credential response (password omitted)."""

    id: uuid.UUID
    node_id: uuid.UUID
    bmc_host: str
    bmc_port: int
    bmc_protocol: str
    bmc_user: str
    last_verified_at: Optional[datetime]
    is_valid: Optional[bool]


# =============================================================================
# Node Group Schemas
# =============================================================================

class NodeGroupBase(BaseModel):
    """Base node group schema."""

    name: str = Field(..., min_length=1, max_length=100, pattern="^[a-zA-Z0-9_-]+$",
                      description="Group name (used in Ansible inventory)")
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None)
    parent_id: Optional[uuid.UUID] = Field(None, description="Parent group for nesting")
    priority: int = Field(0, description="Higher priority = applied last (overrides)")


class NodeGroupCreate(NodeGroupBase):
    """Schema for creating a node group."""

    node_ids: List[uuid.UUID] = Field(default_factory=list, description="Nodes to add to group")
    initial_vars: Dict[str, Any] = Field(default_factory=dict, description="Initial group variables")


class NodeGroupUpdate(BaseModel):
    """Schema for updating a node group."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    priority: Optional[int] = None
    node_ids: Optional[List[uuid.UUID]] = None  # Replace group members


class NodeGroupResponse(NodeGroupBase):
    """Schema for node group response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    is_system: bool
    node_count: int = 0
    created_at: datetime
    updated_at: datetime
    parent_name: Optional[str] = None
    children_names: List[str] = Field(default_factory=list)
    has_vars: bool = False


class NodeGroupListResponse(BaseModel):
    """Schema for paginated node group list."""

    groups: List[NodeGroupResponse]
    pagination: PaginatedResponse


# =============================================================================
# Group Variables Schemas
# =============================================================================

class GroupVarCreate(BaseModel):
    """Schema for creating group variables."""

    vars: Dict[str, Any] = Field(..., description="Variables to apply")
    change_description: Optional[str] = Field(None, description="Description of changes")


class GroupVarUpdate(BaseModel):
    """Schema for updating group variables."""

    vars: Optional[Dict[str, Any]] = None
    merge_strategy: str = Field("replace", pattern="^(replace|merge|delete)$",
                                description="How to merge with existing vars")
    change_description: Optional[str] = None


class GroupVarResponse(BaseModel):
    """Schema for group variable response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    scope: str
    group_id: Optional[uuid.UUID]
    vars: Dict[str, Any]
    version: int
    updated_by: Optional[uuid.UUID]
    change_description: Optional[str]
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Accelerator Schemas
# =============================================================================

class AcceleratorResponse(BaseModel):
    """Schema for accelerator response."""

    id: uuid.UUID
    node_id: uuid.UUID
    type: str
    vendor: Optional[str]
    model: Optional[str]
    device_id: Optional[str]
    slot: Optional[int]
    bus_id: Optional[str]
    numa_node: Optional[int]
    memory_mb: Optional[int]
    cores: Optional[int]
    mig_capable: bool
    mig_mode: Optional[Dict[str, Any]]
    compute_capability: Optional[str]
    driver_version: Optional[str]
    firmware_version: Optional[str]
    health_status: str
    temperature_celsius: Optional[int]
    power_usage_watts: Optional[int]
    utilization_percent: Optional[int]
    discovered_at: datetime


class AcceleratorListResponse(BaseModel):
    """Schema for accelerator list response."""

    accelerators: List[AcceleratorResponse]
    summary: Dict[str, int] = Field(default_factory=dict)


# =============================================================================
# Node Facts Schemas
# =============================================================================

class NodeFactsResponse(BaseModel):
    """Schema for node facts response."""

    id: uuid.UUID
    node_id: uuid.UUID
    collected_at: datetime
    collection_method: str
    ansible_version: Optional[str]

    # OS info
    os_family: Optional[str]
    os_distribution: Optional[str]
    os_version: Optional[str]
    kernel_version: Optional[str]
    architecture: Optional[str]

    # CPU info
    cpu_model: Optional[str]
    cpu_cores: Optional[int]
    cpu_threads_per_core: Optional[int]
    cpu_physical_cores: Optional[int]

    # Memory info
    mem_total_mb: Optional[int]
    swap_total_mb: Optional[int]

    # Network info
    network_interfaces: Optional[Dict[str, Any]]
    default_ipv4: Optional[str]
    default_ipv6: Optional[str]

    # Disk info
    disks: Optional[Dict[str, Any]]
    disk_total_mb: Optional[int]

    # Full facts
    facts: Dict[str, Any]


# =============================================================================
# Job Template Schemas
# =============================================================================

class JobTemplateBase(BaseModel):
    """Base job template schema."""

    name: str = Field(..., min_length=1, max_length=255, pattern="^[a-zA-Z0-9_-]+$",
                      description="Unique template identifier")
    display_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    category: Optional[str] = Field(None, max_length=100)

    # Ansible configuration
    playbook_path: str = Field(..., min_length=1, max_length=500)
    become: bool = True
    become_method: str = "sudo"
    become_user: str = "root"

    # Execution parameters
    timeout_seconds: int = Field(3600, ge=60, le=86400)
    max_retries: int = Field(0, ge=0, le=10)

    # Rolling support
    supports_serial: bool = False
    default_serial: Optional[str] = Field(None, max_length=50)

    # Default vars
    default_vars: Dict[str, Any] = Field(default_factory=dict)

    # Tags
    tags: List[str] = Field(default_factory=list)


class JobTemplateCreate(JobTemplateBase):
    """Schema for creating a job template."""

    input_schema: Optional[Dict[str, Any]] = Field(None, description="JSON Schema for validation")
    input_ui_schema: Optional[Dict[str, Any]] = Field(None, description="UI rendering hints")


class JobTemplateUpdate(BaseModel):
    """Schema for updating a job template."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    playbook_path: Optional[str] = None
    become: Optional[bool] = None
    timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    supports_serial: Optional[bool] = None
    default_serial: Optional[str] = None
    default_vars: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    input_ui_schema: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None


class JobTemplateResponse(JobTemplateBase):
    """Schema for job template response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    enabled: bool
    is_system: bool
    required_roles: List[str]
    version: Optional[str]
    author: Optional[str]
    documentation_url: Optional[str]
    created_at: datetime
    updated_at: datetime


class JobTemplateListResponse(BaseModel):
    """Schema for paginated job template list."""

    templates: List[JobTemplateResponse]
    pagination: PaginatedResponse


# =============================================================================
# Job Run Schemas
# =============================================================================

class JobRunCreate(BaseModel):
    """Schema for creating a job run."""

    template_id: uuid.UUID
    target_type: str = Field(..., pattern="^(node|group|all|adhoc)$")
    target_node_ids: Optional[List[uuid.UUID]] = None
    target_group_ids: Optional[List[uuid.UUID]] = None
    extra_vars: Dict[str, Any] = Field(default_factory=dict)
    serial: Optional[str] = Field(None, max_length=50, description="Serial parameter for rolling updates")


class JobRunResponse(BaseModel):
    """Schema for job run response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    template_id: Optional[uuid.UUID]
    template_name: Optional[str]
    created_by: uuid.UUID
    created_by_email: Optional[str]
    target_type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_seconds: Optional[int]
    summary: Optional[Dict[str, Any]]
    error_message: Optional[str]
    artifacts_bucket: Optional[str]
    artifacts_prefix: Optional[str]
    serial: Optional[str]
    current_batch: int
    total_batches: int
    worker_id: Optional[str]
    node_count: int = 0


class JobRunDetailResponse(JobRunResponse):
    """Extended schema for job run detail."""

    template: Optional[JobTemplateResponse] = None
    nodes: List[NodeResponse] = Field(default_factory=list)
    events_count: int = 0


class JobRunListResponse(BaseModel):
    """Schema for paginated job run list."""

    runs: List[JobRunResponse]
    pagination: PaginatedResponse


class JobRunEventResponse(BaseModel):
    """Schema for job run event response."""

    id: uuid.UUID
    job_run_id: uuid.UUID
    seq: int
    ts: datetime
    event_type: str
    hostname: Optional[str]
    category: Optional[str]
    is_ok: Optional[bool]
    payload: Dict[str, Any]


class JobRunCancel(BaseModel):
    """Schema for canceling a job run."""

    reason: Optional[str] = Field(None, max_length=1000, description="Reason for cancellation")


# =============================================================================
# Audit Log Schemas
# =============================================================================

class AuditLogResponse(BaseModel):
    """Schema for audit log response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    actor_id: uuid.UUID
    actor_email: Optional[str]
    actor_type: str
    action: str
    resource_type: str
    resource_id: Optional[uuid.UUID]
    resource_name: Optional[str]
    diff: Optional[Dict[str, Any]]
    status: str
    error_message: Optional[str]
    ip_address: Optional[str]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log list."""

    logs: List[AuditLogResponse]
    pagination: PaginatedResponse


# =============================================================================
# Prebuilt/Quick Actions Schemas
# =============================================================================

class ConnectivityCheckCreate(BaseModel):
    """Schema for connectivity check job."""

    node_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)


class ConnectivityCheckResponse(BaseModel):
    """Schema for connectivity check result."""

    node_id: uuid.UUID
    node_name: str
    host: str
    port: int
    connection_type: str
    is_reachable: bool
    ssh_reachable: bool
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    checked_at: datetime
    status_before: str
    status_after: str


class BulkConnectivityCheckResponse(BaseModel):
    """Schema for bulk connectivity check result."""

    checked_count: int
    reachable_count: int
    unreachable_count: int
    results: List[ConnectivityCheckResponse]
    checked_at: datetime


class FactsCollectionCreate(BaseModel):
    """Schema for facts collection job."""

    node_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)
    force_refresh: bool = False


class DriverInstallCreate(BaseModel):
    """Schema for driver installation job."""

    node_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)
    driver_type: str = Field(..., pattern="^(nvidia|amd|intel|ascend)$")
    driver_version: Optional[str] = Field(None, description="Specific driver version")
    reboot: bool = Field(False, description="Reboot after installation if needed")
    serial: Optional[str] = Field(None, description="Serial for rolling reboots")


class MonitoringDeployCreate(BaseModel):
    """Schema for monitoring deployment job."""

    node_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)
    exporters: List[str] = Field(default_factory=lambda: ["node_exporter"],
                                  description="Exporters to deploy")
    prometheus_url: Optional[str] = Field(None, description="Prometheus server URL")


# =============================================================================
# Stats/Dashboard Schemas
# =============================================================================

class NodeStatsResponse(BaseModel):
    """Schema for node statistics."""

    total: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    by_accelerator: Dict[str, int]
    unreachable: int
    maintenance: int


class JobStatsResponse(BaseModel):
    """Schema for job statistics."""

    total: int
    running: int
    pending: int
    succeeded: int
    failed: int
    canceled: int
    success_rate: float


class DashboardStatsResponse(BaseModel):
    """Schema for dashboard statistics."""

    nodes: NodeStatsResponse
    jobs: JobStatsResponse
    accelerators: Dict[str, int]
    total_accelerators: int


# =============================================================================
# Cloud Inventory Schemas
# =============================================================================

class CloudProviderCredentials(BaseModel):
    """Base schema for cloud provider credentials."""

    provider: str = Field(..., pattern="^(aws|azure|gcp)$", description="Cloud provider name")


class AWSCredentials(CloudProviderCredentials):
    """AWS credential configuration."""

    provider: str = "aws"
    access_key_id: Optional[str] = Field(None, description="AWS Access Key ID")
    secret_access_key: Optional[str] = Field(None, description="AWS Secret Access Key")
    session_token: Optional[str] = Field(None, description="AWS Session Token (for temp creds)")
    region: str = Field("us-east-1", description="Default AWS region")
    assume_role_arn: Optional[str] = Field(None, description="IAM Role ARN to assume")
    profile_name: Optional[str] = Field(None, description="AWS CLI profile name")


class AzureCredentials(CloudProviderCredentials):
    """Azure credential configuration."""

    provider: str = "azure"
    subscription_id: str = Field(..., description="Azure Subscription ID")
    tenant_id: Optional[str] = Field(None, description="Azure AD Tenant ID")
    client_id: Optional[str] = Field(None, description="Service Principal Client ID")
    client_secret: Optional[str] = Field(None, description="Service Principal Client Secret")
    use_managed_identity: bool = Field(False, description="Use managed identity auth")


class GCPCredentials(CloudProviderCredentials):
    """GCP credential configuration."""

    provider: str = "gcp"
    project_id: str = Field(..., description="GCP Project ID")
    credentials_json: Optional[str] = Field(None, description="Service account JSON (as string)")
    service_account_file: Optional[str] = Field(None, description="Path to service account file")


class CloudDiscoveryRequest(BaseModel):
    """Request to discover nodes from cloud provider."""

    provider: str = Field(..., pattern="^(aws|azure|gcp)$")
    credentials: Union[AWSCredentials, AzureCredentials, GCPCredentials]
    regions: Optional[List[str]] = Field(None, description="Specific regions to scan")
    filters: Optional[Dict[str, Any]] = Field(None, description="Provider-specific filters")


class CloudDiscoveredNodeResponse(BaseModel):
    """Response schema for a discovered cloud node."""

    instance_id: str
    name: str
    private_ip: Optional[str]
    public_ip: Optional[str]
    platform: str  # linux, windows
    instance_type: str
    region: str
    zone: Optional[str]
    state: str
    tags: Dict[str, str]
    labels: Dict[str, str]
    cloud_provider: str
    vpc_id: Optional[str]
    subnet_id: Optional[str]
    security_groups: List[str]
    launch_time: Optional[datetime]
    metadata: Dict[str, Any]


class CloudDiscoveryResponse(BaseModel):
    """Response for cloud discovery operation."""

    provider: str
    discovered_count: int
    regions_scanned: List[str]
    nodes: List[CloudDiscoveredNodeResponse]
    errors: List[str] = Field(default_factory=list)
    discovered_at: datetime


class CloudNodeImportRequest(BaseModel):
    """Request to import discovered cloud nodes."""

    provider: str = Field(..., pattern="^(aws|azure|gcp)$")
    instance_ids: List[str] = Field(..., min_items=1, description="Instance IDs to import")
    use_public_ip: bool = Field(False, description="Use public IP for connectivity")
    default_ssh_user: Optional[str] = Field(None, description="Default SSH user override")
    default_port: int = Field(22, ge=1, le=65535, description="Default SSH/WinRM port")
    group_ids: List[uuid.UUID] = Field(default_factory=list, description="Groups to add nodes to")
    credential_type: str = Field("ssh_key", pattern="^(ssh_key|password|winrm)$")
    ssh_private_key: Optional[str] = Field(None, description="SSH key for all imported nodes")
    password: Optional[str] = Field(None, description="Password for all imported nodes")
    auto_verify: bool = Field(True, description="Verify connectivity after import")


class CloudNodeImportResponse(BaseModel):
    """Response for cloud node import operation."""

    imported_count: int
    failed_count: int
    imported_nodes: List[NodeResponse]
    failed_imports: List[Dict[str, Any]]
    imported_at: datetime
