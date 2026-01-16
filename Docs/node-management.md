# Node Management Module

## Overview

The Node Management module provides enterprise-grade infrastructure management for heterogeneous compute clusters. It enables agentless node onboarding, hardware discovery, and automated configuration management using Ansible as the execution engine.

**Key Capabilities:**
- Agentless SSH-based node management
- Heterogeneous hardware support (NVIDIA/AMD/Intel GPU, Huawei/T-Head NPU)
- Ansible-based job execution with real-time logging
- Encrypted credential storage (AES-256-GCM)
- DeepOps-style node grouping and variable layering

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Frontend (React)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ Node List   │  │ Node Detail │  │ Add Wizard  │  │ Job Center │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST API
┌──────────────────────────────▼──────────────────────────────────────┐
│                        Backend (FastAPI)                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ Node API    │  │ Job API     │  │ Group API   │  │ Cred API   │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │
│         │                │                │                │        │
│  ┌──────▼────────────────▼────────────────▼────────────────▼──────┐ │
│  │                     Node Management Service                     │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │ │
│  │  │ Job Executor │  │ Cred Manager │  │ Accelerator Provider │  │ │
│  │  └───────┬──────┘  └──────────────┘  └──────────────────────┘  │ │
│  └──────────│─────────────────────────────────────────────────────┘ │
└─────────────│───────────────────────────────────────────────────────┘
              │ Redis Queue
┌─────────────▼───────────────────────────────────────────────────────┐
│                     Ansible Runner Worker                            │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ ansible-runner  │  │ Event Stream │  │ Artifact Upload (MinIO)│ │
│  └─────────────────┘  └──────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
              │ SSH
┌─────────────▼───────────────────────────────────────────────────────┐
│                      Managed Nodes                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ GPU Server 1 │  │ NPU Server 2 │  │ CPU Server 3 │  ...         │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Model

### Core Entities

#### Node
```python
class Node:
    id: UUID
    tenant_id: UUID
    name: str                    # Ansible inventory name
    display_name: str            # Human-readable name
    host: str                    # IP or hostname
    port: int                    # SSH port (default: 22)
    connection_type: str         # 'ssh' or 'local'
    ssh_user: str
    status: NodeStatus           # NEW, READY, UNREACHABLE, MAINTENANCE, DECOMMISSIONED
    tags: List[str]
    facts: Dict                  # Collected hardware facts
    credential_id: UUID          # Reference to encrypted credentials
```

#### Accelerator
```python
class Accelerator:
    id: UUID
    node_id: UUID
    device_type: str             # nvidia_gpu, amd_gpu, intel_gpu, huawei_npu, thead_npu
    vendor: str
    model: str
    device_index: int
    pci_address: str
    memory_total: int            # Bytes
    driver_version: str
    compute_capability: str
    health_status: str
```

#### JobTemplate
```python
class JobTemplate:
    id: UUID
    tenant_id: UUID
    name: str                    # Unique identifier
    display_name: str
    description: str
    category: str                # discovery, drivers, monitoring, custom
    playbook_path: str
    become: bool
    become_method: str           # sudo, su
    become_user: str             # root
    timeout_seconds: int
    default_vars: Dict
    tags: List[str]
    is_system: bool              # Built-in templates
```

#### JobRun
```python
class JobRun:
    id: UUID
    tenant_id: UUID
    template_id: UUID
    status: JobStatus            # PENDING, RUNNING, SUCCEEDED, FAILED, CANCELED
    started_at: datetime
    finished_at: datetime
    target_nodes: List[UUID]
    extra_vars: Dict
    serial: int                  # Rolling update batch size
    created_by: UUID
    stats: Dict                  # ok, changed, failed, unreachable counts
    log: str                     # Real-time execution log
```

#### NodeGroup
```python
class NodeGroup:
    id: UUID
    tenant_id: UUID
    name: str
    display_name: str
    description: str
    is_system: bool
    priority: int                # Variable precedence
```

## API Reference

### Nodes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/nodes` | List all nodes |
| POST | `/api/v1/nodes` | Create a new node |
| GET | `/api/v1/nodes/{id}` | Get node details |
| PUT | `/api/v1/nodes/{id}` | Update node |
| DELETE | `/api/v1/nodes/{id}` | Delete node |
| POST | `/api/v1/nodes/{id}/collect-facts` | Trigger fact collection |
| GET | `/api/v1/nodes/{id}/accelerators` | List node accelerators |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/job-templates` | List job templates |
| GET | `/api/v1/job-templates/{id}` | Get template details |
| POST | `/api/v1/jobs` | Create and run a job |
| GET | `/api/v1/jobs` | List job runs |
| GET | `/api/v1/jobs/{id}` | Get job details |
| POST | `/api/v1/jobs/{id}/cancel` | Cancel running job |
| GET | `/api/v1/jobs/{id}/log` | Stream job log |

### Groups

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/node-groups` | List groups |
| POST | `/api/v1/node-groups` | Create group |
| PUT | `/api/v1/node-groups/{id}` | Update group |
| DELETE | `/api/v1/node-groups/{id}` | Delete group |
| GET | `/api/v1/node-groups/{id}/vars` | Get group variables |
| PUT | `/api/v1/node-groups/{id}/vars` | Update group variables |

## Configuration

### Environment Variables

```bash
# Credential Encryption
CREDENTIAL_MASTER_PASSWORD=your-master-password    # Required, AES-256-GCM key derivation
CREDENTIAL_KEY_VERSION=1                           # Key rotation version

# Ansible Configuration
ANSIBLE_WORK_DIR=/var/lib/noveris/ansible          # Working directory
ANSIBLE_PLAYBOOK_REPO_PATH=/app/ansible/playbooks  # Playbook location
ANSIBLE_SSH_ARGS=-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null

# Job Runner
JOB_QUEUE_NAME=ansible_jobs                        # Redis queue name
JOB_RUNNER_CONCURRENCY=4                           # Max concurrent jobs per worker
JOB_CANCEL_GRACE_PERIOD=30                         # Seconds to wait before force kill

# Node Management
NODE_ARTIFACTS_BUCKET=noveris-artifacts            # MinIO bucket for job artifacts
DEFAULT_TENANT_ID=00000000-0000-0000-0000-000000001
```

### Docker Compose (Worker)

```yaml
services:
  ansible-worker:
    build:
      context: ../../../Backend
      dockerfile: Dockerfile.worker
    image: noveris-ansible-worker:latest
    environment:
      DB_DSN: postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      REDIS_DSN: redis://:${REDIS_PASSWORD}@redis:6379/0
      CREDENTIAL_MASTER_PASSWORD: ${CREDENTIAL_MASTER_PASSWORD}
      JOB_QUEUE_NAME: ansible_jobs
      JOB_RUNNER_CONCURRENCY: 4
    volumes:
      - ../../../Backend/app/ansible/playbooks:/app/ansible/playbooks:ro
      - ansible-work:/var/lib/noveris/ansible
      - ansible-keys:/var/lib/noveris/ansible/keys
    deploy:
      replicas: 1
      resources:
        limits:
          memory: 2G
          cpus: '2'
```

## Credential Security

### Encryption Scheme

All sensitive credentials are encrypted using AES-256-GCM before storage:

```python
# Key Derivation
key = PBKDF2(
    password=CREDENTIAL_MASTER_PASSWORD,
    salt=random_salt(16),
    iterations=100000,
    dkLen=32,  # 256-bit key
    hash=SHA256
)

# Encryption
ciphertext = AES-GCM-Encrypt(
    key=key,
    plaintext=credential_data,
    aad=credential_id  # Additional authenticated data
)

# Storage format
stored = base64(salt || nonce || ciphertext || tag)
```

### Credential Types

| Type | Fields Encrypted |
|------|-----------------|
| SSH Key | private_key, passphrase |
| SSH Password | password |
| Bastion | bastion_password |

### Key Rotation

1. Update `CREDENTIAL_KEY_VERSION` in environment
2. Run migration script: `python scripts/rotate_credentials.py`
3. Old credentials automatically re-encrypted with new key

## Hardware Detection

### Supported Accelerators

| Vendor | Type | Detection Tool | Fact Key |
|--------|------|----------------|----------|
| NVIDIA | GPU | nvidia-smi | `nvidia_gpus` |
| AMD | GPU | amd-smi / rocm-smi | `amd_gpus` |
| Intel | GPU | xpu-smi | `intel_gpus` |
| Huawei | NPU | npu-smi | `ascend_npus` |
| T-Head | NPU | thead-smi | `thead_npus` |

### Fact Collection Playbook

The `collect_facts.yml` playbook gathers:

```yaml
# System Facts
ansible_facts:
  architecture: x86_64
  distribution: Ubuntu
  distribution_version: "22.04"
  kernel: 5.15.0-generic
  processor_count: 64
  memtotal_mb: 512000
  mounts: [...]

# Custom Facts
custom_facts:
  nvidia_gpus:
    - index: 0
      name: "NVIDIA A100-SXM4-80GB"
      memory_total: 85899345920
      driver_version: "535.154.05"
      cuda_version: "12.2"
      pci_address: "0000:07:00.0"

  ascend_npus:
    - index: 0
      name: "Ascend 910B"
      memory_total: 65536000000
      driver_version: "24.1.rc1"
      cann_version: "8.0.RC1"
```

## Job Templates

### Built-in Templates

| Name | Category | Description |
|------|----------|-------------|
| `collect_facts` | discovery | Collect hardware facts and accelerator details |
| `connectivity_check` | discovery | Verify SSH connectivity |
| `install_nvidia_driver` | drivers | Install NVIDIA driver + CUDA |
| `install_amd_driver` | drivers | Install AMD ROCm driver |
| `install_intel_driver` | drivers | Install Intel oneAPI driver |
| `install_ascend_driver` | drivers | Install Huawei CANN toolkit |
| `deploy_node_exporter` | monitoring | Deploy Prometheus node_exporter |
| `deploy_dcgm_exporter` | monitoring | Deploy NVIDIA DCGM exporter |

### Template Variables

```yaml
# install_nvidia_driver defaults
nvidia_driver_version: "535"
install_cuda: true
install_fabricmanager: false

# install_ascend_driver defaults
cann_version: "8.0.RC1"
ascend_driver_version: "24.1.rc1"

# deploy_dcgm_exporter defaults
dcgm_exporter_port: 9400
deploy_mode: "systemd"  # or "docker"
```

### Custom Templates

Create custom templates via API:

```json
POST /api/v1/job-templates
{
  "name": "custom_setup",
  "display_name": "Custom Node Setup",
  "category": "custom",
  "playbook_path": "custom/setup.yml",
  "become": true,
  "timeout_seconds": 1800,
  "default_vars": {
    "setup_docker": true,
    "setup_monitoring": true
  }
}
```

## Node Groups & Variables

### Variable Layering

Variables are merged with the following precedence (lower overrides higher):

1. **Global vars** (`scope: all`)
2. **Group vars** (by group priority, lower number = higher precedence)
3. **Node vars** (per-node overrides)
4. **Job extra_vars** (runtime overrides)

### Example Configuration

```python
# Global vars (priority: lowest)
{
    "ansible_python_interpreter": "/usr/bin/python3",
    "ansible_ssh_common_args": "-o StrictHostKeyChecking=no",
    "gather_facts_timeout": 30
}

# Group vars: gpu_nodes (priority: 10)
{
    "install_nvidia_driver": true,
    "nvidia_driver_version": "535"
}

# Node vars: specific node override
{
    "nvidia_driver_version": "550"  # Override for this node only
}
```

## Frontend Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/dashboard/nodes` | NodeListPage | Node list with filters |
| `/dashboard/nodes/add` | AddNodePage | Multi-step add wizard |
| `/dashboard/nodes/:id` | NodeDetailPage | Node details + tabs |
| `/dashboard/jobs` | JobListPage | Job run history |
| `/dashboard/jobs/:id` | JobDetailPage | Job log + stats |

## Database Migration

Initialize the node management tables:

```bash
# Generate migration
alembic revision --autogenerate -m "add node management tables"

# Apply migration
alembic upgrade head

# Seed default data
python scripts/seed_node_management.py
```

### Tables Created

- `nodes` - Node registry
- `accelerators` - Hardware accelerator inventory
- `node_credentials` - Encrypted credentials
- `node_groups` - Node grouping
- `node_group_members` - Node-group membership
- `group_vars` - Group-level variables
- `job_templates` - Job template definitions
- `job_runs` - Job execution history

## Troubleshooting

### Common Issues

**Node unreachable after creation:**
1. Verify SSH connectivity: `ssh -p <port> <user>@<host>`
2. Check credential configuration
3. Review bastion settings if applicable
4. Check firewall rules

**Fact collection fails:**
1. Ensure Python 3 is installed on target node
2. Verify sudo/become permissions
3. Check detection tool availability (nvidia-smi, etc.)

**Job stuck in PENDING:**
1. Verify Redis connectivity
2. Check worker is running: `docker logs noveris-ansible-worker`
3. Review queue status: `redis-cli LLEN ansible_jobs`

**Credential decryption fails:**
1. Verify `CREDENTIAL_MASTER_PASSWORD` matches the one used for encryption
2. Check `CREDENTIAL_KEY_VERSION` consistency

### Log Locations

| Component | Log Location |
|-----------|--------------|
| Backend API | `docker logs noveris-backend` |
| Ansible Worker | `docker logs noveris-ansible-worker` |
| Job Artifacts | MinIO bucket: `noveris-artifacts/{job_id}/` |

## Security Considerations

1. **Credential Storage**: All credentials encrypted at rest with AES-256-GCM
2. **Key Management**: Master password never stored, only in environment
3. **Network Security**: SSH connections use host key checking (configurable)
4. **Access Control**: All operations require authenticated session
5. **Audit Trail**: Job runs logged with user attribution
6. **Multi-tenancy**: Strict tenant isolation via `tenant_id`

## Performance Tuning

### Worker Scaling

```yaml
# Increase concurrent jobs
JOB_RUNNER_CONCURRENCY: 8

# Scale workers horizontally
deploy:
  replicas: 3
```

### Large Cluster Recommendations

- Use bastion hosts for segmented networks
- Enable rolling updates with `serial` parameter
- Configure appropriate timeouts for long-running jobs
- Use group-based targeting to limit blast radius
