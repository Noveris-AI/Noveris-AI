"""
Node Management Database Models.

This module contains all database models for the Node Management system including:
- Nodes (managed servers)
- Node Credentials (encrypted SSH keys, passwords, BMC credentials)
- Node Groups (inventory groups for organization)
- Group Variables (DeepOps-style variable layering)
- Accelerators (GPU/NPU discovery and tracking)
- Node Facts Snapshots (hardware facts collected by Ansible)
- Job Templates (reusable Ansible playbook templates)
- Job Runs (executions of job templates)
- Job Run Events (event stream for logs)
- Audit Logs (compliance and audit trail)
"""

import enum
import json
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
    JSON,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class NodeStatus(str, enum.Enum):
    """Node status enumeration following enterprise standards."""

    NEW = "NEW"                   # Newly added, not yet verified
    READY = "READY"               # Verified and ready for jobs
    UNREACHABLE = "UNREACHABLE"   # Cannot connect
    MAINTENANCE = "MAINTENANCE"   # Under maintenance, no jobs
    DECOMMISSIONED = "DECOMMISSIONED"  # Removed from service


class ConnectionType(str, enum.Enum):
    """Connection type for node management."""

    SSH = "ssh"
    LOCAL = "local"
    WINRM = "winrm"  # Reserved for future use


class JobStatus(str, enum.Enum):
    """Job execution status following CI/CD standards."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    TIMEOUT = "TIMEOUT"


class AuthType(str, enum.Enum):
    """Authentication type for credentials."""

    SSH_KEY = "ssh_key"
    PASSWORD = "password"
    API_KEY = "api_key"  # For BMC/API access


class BmcProtocol(str, enum.Enum):
    """BMC (Baseboard Management Controller) protocol."""

    REDFISH = "redfish"
    IPMI = "ipmi"
    NONE = "none"


class AcceleratorType(str, enum.Enum):
    """Accelerator device types."""

    NVIDIA_GPU = "nvidia_gpu"
    AMD_GPU = "amd_gpu"
    INTEL_GPU = "intel_gpu"
    ASCEND_NPU = "ascend_npu"
    T_HEAD_NPU = "t_head_npu"
    GENERIC_ACCEL = "generic_accel"


class NodeType(str, enum.Enum):
    """Node type classification."""

    MANAGEMENT = "management"     # Control plane nodes
    COMPUTE = "compute"           # GPU/NPU compute nodes
    LOGIN = "login"               # User access nodes
    STORAGE = "storage"           # Storage nodes
    KUBE_NODE = "kube_node"       # Kubernetes worker
    KUBE_MASTER = "kube_master"   # Kubernetes control plane
    SLURM_NODE = "slurm_node"     # Slurm compute node
    SLURM_CTRL = "slurm_ctrl"     # Slurm controller
    EDGE = "edge"                 # Edge inference nodes
    GENERIC = "generic"           # Generic/unclassified


# Association table for Node <-> NodeGroup many-to-many
node_group_association = Table(
    "node_group_association",
    Base.metadata,
    Column("node_id", UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True),
    Column("node_group_id", UUID(as_uuid=True), ForeignKey("node_groups.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for JobRun <-> Node many-to-many
job_run_nodes = Table(
    "job_run_nodes",
    Base.metadata,
    Column("job_run_id", UUID(as_uuid=True), ForeignKey("job_runs.id", ondelete="CASCADE"), primary_key=True),
    Column("node_id", UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True),
)


class Node(Base):
    """
    Managed Node model.

    Represents a Linux server under platform management.
    Supports SSH and local (control plane node) connections.
    """

    __tablename__ = "nodes"
    __table_args__ = (
        Index("ix_nodes_tenant_id", "tenant_id"),
        Index("ix_nodes_status", "status"),
        Index("ix_nodes_host", "host"),
        Index("ix_nodes_last_seen", "last_seen_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)  # Index defined in __table_args__

    # Basic identification
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))  # Human-readable display name
    host = Column(String(255), nullable=False)  # IP or hostname
    port = Column(Integer, default=22)  # SSH port (default 22)

    # Connection settings
    connection_type = Column(Enum(ConnectionType, create_type=False), default=ConnectionType.SSH, nullable=False)
    ssh_user = Column(String(100))  # SSH username
    status = Column(Enum(NodeStatus, create_type=False), default=NodeStatus.NEW, nullable=False)  # Index defined in __table_args__

    # Organization
    node_type = Column(Enum(NodeType, create_type=False), default=NodeType.GENERIC)
    labels = Column(JSONB, default=dict)  # Flexible labels for scheduling
    tags = Column(ARRAY(String), default=list)  # Simple tags for filtering

    # Relationships
    credentials = relationship("NodeCredential", back_populates="node", uselist=False, cascade="all, delete-orphan")
    bmc_credentials = relationship("NodeBmcCredential", back_populates="node", uselist=False, cascade="all, delete-orphan")
    accelerators = relationship("Accelerator", back_populates="node", cascade="all, delete-orphan")
    fact_snapshots = relationship("NodeFactSnapshot", back_populates="node", cascade="all, delete-orphan", order_by="NodeFactSnapshot.collected_at.desc()")
    groups = relationship("NodeGroup", secondary=node_group_association, back_populates="nodes", lazy="selectin")

    # Hardware info (cached from last fact collection)
    os_release = Column(String(100))  # e.g., "Ubuntu 22.04"
    kernel_version = Column(String(100))
    cpu_cores = Column(Integer)
    cpu_model = Column(String(255))
    mem_mb = Column(Integer)  # Total memory in MB
    disk_mb = Column(Integer)  # Total disk in MB
    architecture = Column(String(50))  # x86_64, aarch64, etc.

    # Monitoring state
    last_seen_at = Column(DateTime(timezone=True))
    last_job_run_at = Column(DateTime(timezone=True))
    last_job_id = Column(UUID(as_uuid=True))
    connectivity_errors = Column(JSONB, default=list)  # Track recent errors

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    decommissioned_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<Node(id={self.id}, name={self.name}, host={self.host}, status={self.status.value})>"


class NodeCredential(Base):
    """
    Node credentials with encrypted storage.

    Supports SSH key and password authentication.
    Payload is encrypted using AES-GCM with master key from environment.
    """

    __tablename__ = "node_credentials"
    __table_args__ = (
        Index("ix_node_credentials_tenant_id", "tenant_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)  # Index defined in __table_args__
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Authentication type
    auth_type = Column(Enum(AuthType, create_type=False), nullable=False)

    # Encrypted payload (JSON string containing key/password)
    # Structure for ssh_key: {"private_key": "...", "passphrase": "..."}
    # Structure for password: {"password": "..."}
    encrypted_payload = Column(Text, nullable=False)  # Base64 encoded encrypted data
    key_version = Column(Integer, default=1)  # For key rotation support

    # Optional bastion/jump host configuration
    bastion_host = Column(String(255))  # Jump host address
    bastion_port = Column(Integer, default=22)
    bastion_user = Column(String(100))
    encrypted_bastion_auth = Column(Text)  # Encrypted bastion credential
    bastion_key_version = Column(Integer)

    # Metadata
    last_rotated_at = Column(DateTime(timezone=True))
    last_used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship
    node = relationship("Node", back_populates="credentials")

    def __repr__(self):
        return f"<NodeCredential(id={self.id}, node_id={self.node_id}, auth_type={self.auth_type.value})>"


class NodeBmcCredential(Base):
    """
    BMC (Baseboard Management Controller) credentials.

    Optional credentials for Redfish/IPMI access to manage BIOS/firmware.
    Only used when user provides BMC credentials.
    """

    __tablename__ = "node_bmc_credentials"
    __table_args__ = (
        Index("ix_node_bmc_credentials_tenant_id", "tenant_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)  # Index defined in __table_args__
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), unique=True, nullable=False)

    # BMC connection info
    bmc_host = Column(String(255), nullable=False)  # BMC IP/hostname
    bmc_port = Column(Integer, default=443)  # Redfish typically 443, IPMI 623
    bmc_protocol = Column(Enum(BmcProtocol, create_type=False), default=BmcProtocol.REDFISH)
    bmc_user = Column(String(100), nullable=False)

    # Encrypted password
    encrypted_password = Column(Text, nullable=False)
    key_version = Column(Integer, default=1)

    # Verification
    last_verified_at = Column(DateTime(timezone=True))
    is_valid = Column(Boolean, default=None)  # None=not checked, True/False=verified

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship
    node = relationship("Node", back_populates="bmc_credentials")

    def __repr__(self):
        return f"<NodeBmcCredential(id={self.id}, node_id={self.node_id}, protocol={self.bmc_protocol.value})>"


class NodeGroup(Base):
    """
    Node Group for inventory organization.

    Following Ansible/DeepOps best practices:
    - Groups represent inventory groups (compute, storage, gpu-nvidia, etc.)
    - Groups can have variables (group_vars) applied to all members
    - Groups can be nested (parent_id)
    """

    __tablename__ = "node_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_node_group_tenant_name"),
        Index("ix_node_groups_tenant_id", "tenant_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)  # Index defined in __table_args__

    # Group info
    name = Column(String(100), nullable=False)  # Used as Ansible group name
    display_name = Column(String(255))
    description = Column(Text)

    # Hierarchy support (for nested groups)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("node_groups.id"))
    priority = Column(Integer, default=0)  # Higher priority = applied last (overrides)

    # Relationships
    parent = relationship("NodeGroup", remote_side=[id], backref="children")
    nodes = relationship("Node", secondary=node_group_association, back_populates="groups", lazy="selectin")
    group_vars = relationship("GroupVar", back_populates="group", cascade="all, delete-orphan")

    # Metadata
    is_system = Column(Boolean, default=False)  # System groups cannot be deleted
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<NodeGroup(id={self.id}, name={self.name}, tenant_id={self.tenant_id})>"


class GroupVar(Base):
    """
    Group Variables (Ansible group_vars).

    Implements DeepOps-style variable layering:
    - scope='all': Global variables applied to all nodes
    - scope='group': Variables applied to specific group
    """

    __tablename__ = "group_vars"
    __table_args__ = (
        Index("ix_group_vars_tenant_id", "tenant_id"),
        Index("ix_group_vars_scope", "scope"),
        Index("ix_group_vars_group_id", "group_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)  # Index defined in __table_args__

    # Scope: 'all' for global, 'group' for specific group
    scope = Column(String(20), nullable=False)  # 'all' or 'group'
    group_id = Column(UUID(as_uuid=True), ForeignKey("node_groups.id", ondelete="CASCADE"), nullable=True)  # NULL when scope='all'

    # Variables (YAML-compatible structure)
    vars = Column(JSONB, nullable=False, default=dict)

    # Version tracking
    version = Column(Integer, default=1)
    updated_by = Column(UUID(as_uuid=True))  # User who made the change
    change_description = Column(Text)  # Optional description of the change

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    group = relationship("NodeGroup", back_populates="group_vars")

    def __repr__(self):
        return f"<GroupVar(id={self.id}, scope={self.scope}, group_id={self.group_id})>"


class NodeFactSnapshot(Base):
    """
    Hardware facts snapshot collected by Ansible.

    Stores complete hardware discovery results including:
    - CPU, memory, disk, network
    - GPU/NPU details (via Accelerator records)
    - Driver and toolkit versions
    """

    __tablename__ = "node_fact_snapshots"
    __table_args__ = (
        Index("ix_node_fact_snapshots_node_id", "node_id"),
        Index("ix_node_fact_snapshots_collected_at", "collected_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)

    # Full facts from Ansible
    facts = Column(JSONB, nullable=False, default=dict)

    # Quick access fields (denormalized for queries)
    os_family = Column(String(50))  # debian, redhat, etc.
    os_distribution = Column(String(100))  # ubuntu, centos, etc.
    os_version = Column(String(50))
    kernel_version = Column(String(100))
    architecture = Column(String(50))

    cpu_model = Column(String(255))
    cpu_cores = Column(Integer)
    cpu_threads_per_core = Column(Integer)
    cpu_physical_cores = Column(Integer)

    mem_total_mb = Column(Integer)
    swap_total_mb = Column(Integer)

    # Network info
    network_interfaces = Column(JSONB)  # List of interfaces with IPs, MACs
    default_ipv4 = Column(String(50))
    default_ipv6 = Column(String(50))

    # Disk info
    disks = Column(JSONB)  # Disk devices and mount points
    disk_total_mb = Column(Integer)

    # Collection metadata
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    collection_method = Column(String(50), default="ansible")  # ansible, manual, api
    ansible_version = Column(String(50))

    # Relationships
    node = relationship("Node", back_populates="fact_snapshots")

    def __repr__(self):
        return f"<NodeFactSnapshot(id={self.id}, node_id={self.node_id}, collected_at={self.collected_at})>"


class Accelerator(Base):
    """
    Accelerator (GPU/NPU) device information.

    Collected during fact collection and updated independently.
    Supports NVIDIA (with MIG), AMD, Intel, Huawei Ascend, and generic PCI devices.
    """

    __tablename__ = "accelerators"
    __table_args__ = (
        Index("ix_accelerators_node_id", "node_id"),
        Index("ix_accelerators_type", "type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)

    # Device type and identification
    type = Column(Enum(AcceleratorType, create_type=False), nullable=False)
    vendor = Column(String(100))  # nvidia, amd, intel, huawei, t-head, unknown
    model = Column(String(255))  # e.g., "A100-SXM4-80GB", "MI250X"
    device_id = Column(String(100))  # PCI device ID or UUID

    # Position and topology
    slot = Column(Integer)  # PCI slot number
    bus_id = Column(String(50))  # PCI bus ID (e.g., "0000:03:00.0")
    numa_node = Column(Integer)  # NUMA node affinity
    topology = Column(JSONB, default=dict)  # Topology info (NVLink, etc.)

    # Capacity
    count = Column(Integer, default=1)  # For multi-card devices
    memory_mb = Column(Integer)  # Total memory in MB
    cores = Column(Integer)  # For multi-core accelerators

    # Capabilities
    mig_capable = Column(Boolean, default=False)  # NVIDIA MIG support
    mig_mode = Column(JSONB)  # MIG mode configuration (enabled/disabled/partitions)
    compute_capability = Column(String(20))  # e.g., "8.0" for NVIDIA

    # Driver/toolchain versions
    driver_version = Column(String(100))
    firmware_version = Column(String(100))
    toolkit_version = Column(String(100))  # cuda, rocm, etc.

    # Health and utilization (from monitoring)
    health_status = Column(String(50), default="unknown")  # healthy, degraded, error, unknown
    temperature_celsius = Column(Integer)  # Last temperature reading
    power_usage_watts = Column(Integer)  # Last power usage
    utilization_percent = Column(Integer)  # Last GPU utilization

    # Metadata
    pci_vendor_id = Column(String(10))  # e.g., "10de" for NVIDIA
    pci_device_id = Column(String(10))  # e.g., "20bf" for A100
    subsystem_vendor_id = Column(String(10))
    subsystem_device_id = Column(String(10))

    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    node = relationship("Node", back_populates="accelerators")

    def __repr__(self):
        return f"<Accelerator(id={self.id}, type={self.type.value}, model={self.model})>"


class JobTemplate(Base):
    """
    Job Template for reusable Ansible playbook execution.

    Represents a pre-configured Ansible operation that can be run
    against nodes or node groups with customizable parameters.
    """

    __tablename__ = "job_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_job_template_tenant_name"),
        Index("ix_job_templates_tenant_id", "tenant_id"),
        Index("ix_job_templates_category", "category"),
        Index("ix_job_templates_enabled", "enabled"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)  # Index defined in __table_args__

    # Template info
    name = Column(String(255), nullable=False, unique=True)  # Unique identifier
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))  # e.g., "bootstrap", "drivers", "monitoring", "bios"

    # Ansible configuration
    playbook_path = Column(String(500), nullable=False)  # Relative to playbook repo
    roles_path = Column(String(500))  # Custom roles path
    collections = Column(JSONB)  # Required collections

    # Execution parameters
    target_type = Column(String(20), nullable=False)  # 'node', 'group', 'all'
    become = Column(Boolean, default=True)
    become_method = Column(String(20), default="sudo")
    become_user = Column(String(50), default="root")

    # Timeout and retry
    timeout_seconds = Column(Integer, default=3600)  # 1 hour default
    max_retries = Column(Integer, default=0)
    retry_delay_seconds = Column(Integer, default=60)

    # Rolling/reboot support
    supports_serial = Column(Boolean, default=False)
    default_serial = Column(String(50))  # e.g., "10%", "3", "30%"

    # Input validation (JSON Schema)
    input_schema = Column(JSONB)  # JSON Schema for extra_vars validation
    input_ui_schema = Column(JSONB)  # UI rendering hints

    # Default variables
    default_vars = Column(JSONB, default=dict)  # Default extra_vars

    # Access control
    enabled = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)  # System templates cannot be deleted
    required_roles = Column(ARRAY(String), default=list)  # Roles that can execute

    # Metadata
    tags = Column(ARRAY(String), default=list)
    version = Column(String(50))  # Template version
    author = Column(String(255))
    documentation_url = Column(String(500))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    job_runs = relationship("JobRun", back_populates="template", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<JobTemplate(id={self.id}, name={self.name}, playbook={self.playbook_path})>"


class JobRun(Base):
    """
    Job Run execution record.

    Represents a single execution of a JobTemplate against specific targets.
    Tracks status, results, and provides access to logs and artifacts.
    """

    __tablename__ = "job_runs"
    __table_args__ = (
        Index("ix_job_runs_tenant_id", "tenant_id"),
        Index("ix_job_runs_template_id", "template_id"),
        Index("ix_job_runs_status", "status"),
        Index("ix_job_runs_created_by", "created_by"),
        Index("ix_job_runs_started_at", "started_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)  # Index defined in __table_args__

    # Template reference
    template_id = Column(UUID(as_uuid=True), ForeignKey("job_templates.id", ondelete="SET NULL"), nullable=True)
    template_snapshot = Column(JSONB)  # Snapshot of template at execution time

    # Execution context
    created_by = Column(UUID(as_uuid=True), nullable=False)  # User ID who initiated
    created_by_email = Column(String(255))  # Email for display

    # Targets (can be direct nodes or via groups)
    target_type = Column(String(20), nullable=False)  # 'node', 'group', 'all', 'adhoc'
    target_node_ids = Column(JSONB)  # List of node IDs
    target_group_ids = Column(JSONB)  # List of group IDs

    # Execution parameters
    extra_vars = Column(JSONB, default=dict)  # User-provided variables
    runtime_vars = Column(JSONB, default=dict)  # Computed vars at runtime
    inventory_content = Column(Text)  # Generated inventory (for debugging)

    # Status tracking
    status = Column(Enum(JobStatus, create_type=False), default=JobStatus.PENDING, nullable=False)  # Index defined in __table_args__

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)

    # Results summary
    summary = Column(JSONB, default=dict)  # {ok, changed, unreachable, failed, skipped}
    error_message = Column(Text)
    error_detail = Column(Text)

    # Artifacts
    artifacts_bucket = Column(String(255))  # MinIO bucket
    artifacts_prefix = Column(String(500))  # Path prefix for artifacts

    # Cancellation
    canceled_at = Column(DateTime(timezone=True))
    canceled_by = Column(UUID(as_uuid=True))
    cancellation_reason = Column(Text)

    # Rolling/serial execution
    serial = Column(String(50))  # Serial parameter used
    current_batch = Column(Integer, default=0)
    total_batches = Column(Integer, default=1)

    # Worker info
    worker_id = Column(String(255))  # Worker that processed this job
    worker_pid = Column(Integer)  # Process ID on worker

    # Relationships
    template = relationship("JobTemplate", back_populates="job_runs")
    nodes = relationship("Node", secondary=job_run_nodes, backref="job_runs", lazy="selectin")
    events = relationship("JobRunEvent", back_populates="job_run", cascade="all, delete-orphan", order_by="JobRunEvent.seq")

    def __repr__(self):
        return f"<JobRun(id={self.id}, status={self.status.value}, template_id={self.template_id})>"


class JobRunEvent(Base):
    """
    Job Run Event for real-time log streaming.

    Stores individual events from Ansible runner for log display.
    Full event stream is also stored in MinIO for download.
    """

    __tablename__ = "job_run_events"
    __table_args__ = (
        Index("ix_job_run_events_job_run_id", "job_run_id"),
        Index("ix_job_run_events_ts", "ts"),
        Index("ix_job_run_events_event_type", "event_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_run_id = Column(UUID(as_uuid=True), ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False)
    seq = Column(Integer, nullable=False)  # Event sequence number

    # Event metadata
    ts = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    event_type = Column(String(50), nullable=False)  # ansible, callback, runner, error, etc.

    # Event payload
    payload = Column(JSONB, nullable=False)  # Full event data

    # For quick filtering
    hostname = Column(String(255))  # Target node
    category = Column(String(50))  # task, handler, playbook, etc.
    is_ok = Column(Boolean)  # Quick success/fail flag

    # Relationship back to JobRun
    job_run = relationship("JobRun", back_populates="events")

    def __repr__(self):
        return f"<JobRunEvent(id={self.id}, job_run_id={self.job_run_id}, event_type={self.event_type}, seq={self.seq})>"


class AuditLog(Base):
    """
    Audit log for compliance and security tracking.

    Records all significant actions in the Node Management system.
    Provides immutable audit trail for regulatory compliance.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_id", "tenant_id"),
        Index("ix_audit_logs_actor_id", "actor_id"),
        Index("ix_audit_logs_resource_type", "resource_type"),
        Index("ix_audit_logs_resource_id", "resource_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)  # Index defined in __table_args__

    # Actor
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    actor_email = Column(String(255))
    actor_type = Column(String(50), default="user")  # user, system, api

    # Action
    action = Column(String(100), nullable=False)  # create, update, delete, execute, etc.
    resource_type = Column(String(100), nullable=False)  # node, credential, job_run, etc.
    resource_id = Column(UUID(as_uuid=True))
    resource_name = Column(String(255))  # Human-readable identifier

    # Change details
    diff = Column(JSONB)  # Before/after for updates
    request_summary = Column(JSONB)  # Sanitized request parameters

    # Result
    status = Column(String(50), default="success")  # success, failure, partial
    error_message = Column(Text)

    # Context
    ip_address = Column(String(50))  # Client IP
    user_agent = Column(String(500))  # Client user agent
    session_id = Column(String(255))  # Session identifier

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, resource_type={self.resource_type}, actor={self.actor_email})>"
