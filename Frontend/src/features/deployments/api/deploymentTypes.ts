/**
 * Model Deployment API Types
 */

// Enums
export type DeploymentStatus =
  | 'PENDING'
  | 'DOWNLOADING'
  | 'INSTALLING'
  | 'STARTING'
  | 'RUNNING'
  | 'STOPPED'
  | 'FAILED'
  | 'DELETING'

export type DeploymentFramework = 'vllm' | 'sglang' | 'xinference'
export type DeploymentMode = 'native' | 'docker'
export type ModelSource = 'huggingface' | 'modelscope' | 'local'
export type HealthStatus = 'unknown' | 'healthy' | 'unhealthy' | 'starting'

// Environment variable table entry
export interface EnvTableEntry {
  name: string
  value: string
  is_sensitive: boolean
}

// CLI arguments table entry
export interface ArgsTableEntry {
  key: string
  value: string
  arg_type: 'string' | 'int' | 'float' | 'bool' | 'json'
  enabled: boolean
}

// Deployment types
export interface Deployment {
  id: string
  tenant_id: string
  name: string
  display_name: string | null
  description: string | null
  framework: DeploymentFramework
  deployment_mode: DeploymentMode
  node_id: string | null
  model_source: ModelSource
  model_repo_id: string
  model_revision: string | null
  model_local_path: string | null
  host: string
  port: number
  served_model_name: string | null
  gpu_devices: number[] | null
  tensor_parallel_size: number
  gpu_memory_utilization: number
  env_table: EnvTableEntry[]
  args_table: ArgsTableEntry[]
  status: DeploymentStatus
  health_status: HealthStatus
  last_health_check_at: string | null
  error_message: string | null
  endpoints: Record<string, string>
  labels: Record<string, string>
  tags: string[]
  created_by: string
  created_by_email: string | null
  created_at: string
  updated_at: string
  started_at: string | null
  stopped_at: string | null
  node_name: string | null
  node_host: string | null
}

export interface DeploymentDetail extends Deployment {
  systemd_service_name: string | null
  systemd_unit_path: string | null
  wrapper_script_path: string | null
  config_json_path: string | null
  log_dir: string | null
  install_job_run_id: string | null
  start_job_run_id: string | null
  stop_job_run_id: string | null
  error_detail: string | null
  retry_count: number
  max_retries: number
  recent_logs: DeploymentLog[]
}

// Deployment Log types
export interface DeploymentLog {
  id: string
  deployment_id: string
  level: string
  message: string
  source: string | null
  operation: string | null
  job_run_id: string | null
  data: Record<string, any> | null
  created_at: string
}

// Compatibility types
export interface FrameworkCompatibility {
  framework: string
  supported: boolean
  reason: string | null
  install_profile: string | null
  capabilities: Record<string, any> | null
  requirements: Record<string, string> | null
}

export interface CompatibilityCheckResult {
  node_id: string
  node_name: string
  node_host: string
  frameworks: FrameworkCompatibility[]
  evaluated_at: string
}

// Accelerator device for selection
export interface AcceleratorDevice {
  index: number
  device_type: string
  vendor: string
  model: string
  memory_mb: number
  uuid: string | null
  health_status: string
  utilization_percent: number | null
}

export interface NodeAccelerators {
  node_id: string
  node_name: string
  accelerator_type: string | null
  accelerator_count: number
  devices: AcceleratorDevice[]
}

// Action response
export interface DeploymentActionResponse {
  deployment_id: string
  action: string
  status: string
  job_run_id: string | null
  message: string
}

// Health check response
export interface DeploymentHealthResponse {
  deployment_id: string
  health_status: string
  last_check_at: string
  endpoints: Record<string, string>
  error: string | null
  response_time_ms: number | null
}

// Log types
export interface LogLine {
  timestamp: string | null
  source: string
  content: string
}

export interface LogStreamResponse {
  deployment_id: string
  lines: LogLine[]
  has_more: boolean
}

// Request types
export interface DeploymentCreateRequest {
  name: string
  display_name?: string
  description?: string
  framework: DeploymentFramework
  deployment_mode?: DeploymentMode
  node_id: string
  model_source?: ModelSource
  model_repo_id: string
  model_revision?: string
  host?: string
  port?: number
  served_model_name?: string
  gpu_devices?: number[]
  tensor_parallel_size?: number
  gpu_memory_utilization?: number
  env_table?: EnvTableEntry[]
  args_table?: ArgsTableEntry[]
  labels?: Record<string, string>
  tags?: string[]
}

export interface DeploymentUpdateRequest {
  display_name?: string
  description?: string
  gpu_devices?: number[]
  tensor_parallel_size?: number
  gpu_memory_utilization?: number
  env_table?: EnvTableEntry[]
  args_table?: ArgsTableEntry[]
  labels?: Record<string, string>
  tags?: string[]
}

export interface CompatibilityCheckRequest {
  node_id: string
  frameworks?: DeploymentFramework[]
}

// Response types
export interface PaginatedResponse {
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface DeploymentListResponse {
  deployments: Deployment[]
  pagination: PaginatedResponse
}

export interface DeploymentLogListResponse {
  logs: DeploymentLog[]
  pagination: PaginatedResponse
}

// Search params
export interface DeploymentSearchParams {
  page?: number
  page_size?: number
  search?: string
  framework?: DeploymentFramework
  status?: DeploymentStatus
  node_id?: string
  tags?: string[]
}

// Stats types
export interface DeploymentStats {
  total: number
  by_status: Record<string, number>
  by_framework: Record<string, number>
  running: number
  failed: number
}

// Framework config template
export interface FrameworkConfigTemplate {
  framework: string
  description: string
  recommended_args: ArgsTableEntry[]
  recommended_env: EnvTableEntry[]
  documentation_url: string
}
