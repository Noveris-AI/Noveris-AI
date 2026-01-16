/**
 * Node Management API Types
 */

// Enums
export type NodeStatus = 'NEW' | 'READY' | 'UNREACHABLE' | 'MAINTENANCE' | 'DECOMMISSIONED'
export type JobStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELED'
export type ConnectionType = 'ssh' | 'local'
export type AcceleratorType = 'nvidia_gpu' | 'amd_gpu' | 'intel_gpu' | 'huawei_npu' | 'thead_npu' | 'other'

// Node types
export interface Node {
  id: string
  tenant_id: string
  name: string
  display_name: string
  host: string
  port: number
  connection_type: ConnectionType
  ssh_user: string
  node_type: string
  labels: Record<string, string>
  tags: string[]
  status: NodeStatus
  os_release?: string
  kernel_version?: string
  cpu_cores?: number
  cpu_model?: string
  mem_mb?: number
  disk_mb?: number
  architecture?: string
  last_seen_at?: string
  last_job_run_at?: string
  created_at: string
  updated_at: string
  group_ids: string[]
  group_names: string[]
  accelerator_summary: Record<string, number>
}

export interface NodeDetail extends Node {
  credentials_exist: boolean
  bmc_configured: boolean
  accelerators: Accelerator[]
  last_facts?: Record<string, any>
}

export interface Accelerator {
  id: string
  node_id: string
  type: AcceleratorType
  vendor: string
  model: string
  device_id: string
  slot?: string
  bus_id?: string
  numa_node?: number
  memory_mb?: number
  cores?: number
  mig_capable?: boolean
  mig_mode?: boolean
  compute_capability?: string
  driver_version?: string
  firmware_version?: string
  health_status?: string
  temperature_celsius?: number
  power_usage_watts?: number
  utilization_percent?: number
  discovered_at: string
}

// Node Group types
export interface NodeGroup {
  id: string
  tenant_id: string
  name: string
  display_name: string
  description?: string
  parent_id?: string
  priority: number
  is_system: boolean
  node_count: number
  created_at: string
  updated_at: string
  parent_name?: string
  children_names: string[]
  has_vars: boolean
}

// Job Template types
export interface JobTemplate {
  id: string
  tenant_id: string
  name: string
  display_name: string
  description?: string
  category: string
  playbook_path: string
  become: boolean
  become_method?: string
  become_user?: string
  timeout_seconds: number
  max_retries: number
  supports_serial: boolean
  default_serial: number
  default_vars: Record<string, any>
  tags: string[]
  enabled: boolean
  is_system: boolean
  required_roles: string[]
  version: string
  author?: string
  documentation_url?: string
  created_at: string
  updated_at: string
}

// Job Run types
export interface JobRun {
  id: string
  tenant_id: string
  template_id: string
  template_name?: string
  created_by: string
  created_by_email?: string
  target_type: string
  status: JobStatus
  created_at: string
  started_at?: string
  finished_at?: string
  duration_seconds?: number
  summary?: Record<string, number>
  error_message?: string
  artifacts_bucket?: string
  artifacts_prefix?: string
  serial: number
  current_batch?: number
  total_batches?: number
  worker_id?: string
  node_count: number
}

export interface JobRunDetail extends JobRun {
  template?: JobTemplate
  nodes: Node[]
  events_count: number
}

export interface JobRunEvent {
  id: string
  job_run_id: string
  seq: number
  ts: string
  event_type: string
  hostname?: string
  category?: string
  is_ok?: boolean
  payload: Record<string, any>
}

// Group Vars types
export interface GroupVar {
  id: string
  tenant_id: string
  scope: string
  group_id?: string
  vars: Record<string, any>
  version: number
  updated_by?: string
  change_description?: string
  created_at: string
  updated_at: string
}

// Statistics types
export interface NodeStats {
  total: number
  by_status: Record<string, number>
  by_type: Record<string, number>
  by_accelerator: Record<string, number>
  unreachable: number
  maintenance: number
}

export interface JobStats {
  total: number
  running: number
  pending: number
  succeeded: number
  failed: number
  canceled: number
  success_rate: number
}

export interface DashboardStats {
  nodes: NodeStats
  jobs: JobStats
  accelerators: Record<string, number>
  total_accelerators: number
}

// Request types
export interface NodeCreateRequest {
  name: string
  display_name?: string
  host: string
  port?: number
  connection_type?: ConnectionType
  ssh_user?: string
  credential_type: 'ssh_key' | 'password'
  ssh_private_key?: string
  ssh_key_passphrase?: string
  password?: string
  bastion_host?: string
  bastion_port?: number
  bastion_user?: string
  bastion_ssh_key?: string
  bastion_password?: string
  group_ids?: string[]
  labels?: Record<string, string>
  tags?: string[]
}

export interface NodeUpdateRequest {
  display_name?: string
  port?: number
  ssh_user?: string
  node_type?: string
  labels?: Record<string, string>
  tags?: string[]
  status?: NodeStatus
  group_ids?: string[]
}

export interface NodeGroupCreateRequest {
  name: string
  display_name?: string
  description?: string
  parent_id?: string
  priority?: number
  initial_vars?: Record<string, any>
  node_ids?: string[]
}

export interface JobRunCreateRequest {
  template_id: string
  target_type: 'node' | 'group' | 'all'
  target_node_ids?: string[]
  target_group_ids?: string[]
  extra_vars?: Record<string, any>
  serial?: number
}

export interface GroupVarUpdateRequest {
  vars: Record<string, any>
  merge_strategy?: 'replace' | 'merge' | 'delete'
  change_description?: string
}

// Response types
export interface PaginatedResponse<T> {
  pagination: {
    total: number
    page: number
    page_size: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
  }
}

export interface NodeListResponse extends PaginatedResponse<Node> {
  nodes: Node[]
}

export interface NodeGroupListResponse extends PaginatedResponse<NodeGroup> {
  groups: NodeGroup[]
}

export interface JobTemplateListResponse extends PaginatedResponse<JobTemplate> {
  templates: JobTemplate[]
}

export interface JobRunListResponse extends PaginatedResponse<JobRun> {
  runs: JobRun[]
}

// Search params
export interface NodeSearchParams {
  page?: number
  page_size?: number
  search?: string
  status?: NodeStatus
  accel_type?: AcceleratorType
  group_id?: string
  tags?: string[]
}

export interface JobRunSearchParams {
  page?: number
  page_size?: number
  status?: JobStatus
  template_id?: string
  node_id?: string
}
