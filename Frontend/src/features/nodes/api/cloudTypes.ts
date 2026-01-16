/**
 * Cloud Discovery API Types
 *
 * TypeScript interfaces for cloud platform node discovery.
 */

// Cloud Providers
export type CloudProvider = 'aws' | 'azure' | 'gcp'

// AWS Credentials
export interface AwsCredentials {
  access_key_id: string
  secret_access_key: string
  session_token?: string
  region: string
}

// Azure Credentials
export interface AzureCredentials {
  subscription_id: string
  client_id: string
  client_secret: string
  tenant_id: string
}

// GCP Credentials
export interface GcpCredentials {
  project_id: string
  service_account_json?: string
  credentials_file?: string
}

// Cloud Credentials (union type)
export type CloudCredentials = AwsCredentials | AzureCredentials | GcpCredentials

// Discovered Instance
export interface DiscoveredInstance {
  instance_id: string
  name: string
  provider: CloudProvider
  region: string
  zone?: string
  state: string
  instance_type: string
  public_ip?: string
  private_ip?: string
  platform?: string
  launch_time?: string
  tags: Record<string, string>
  vpc_id?: string
  subnet_id?: string
  security_groups?: string[]
}

// Discovery Request
export interface CloudDiscoveryRequest {
  provider: CloudProvider
  credentials: CloudCredentials
  regions?: string[]
  filters?: Record<string, string[]>
  include_stopped?: boolean
}

// Discovery Response
export interface CloudDiscoveryResponse {
  provider: CloudProvider
  regions_scanned: string[]
  total_instances: number
  instances: DiscoveredInstance[]
  discovered_at: string
  errors?: Array<{
    region: string
    error: string
  }>
}

// Validate Credentials Request
export interface ValidateCredentialsRequest {
  provider: CloudProvider
  credentials: CloudCredentials
}

// Validate Credentials Response
export interface ValidateCredentialsResponse {
  valid: boolean
  provider: CloudProvider
  account_info?: Record<string, string>
  error?: string
  checked_at: string
}

// Import from Cloud Request
export interface CloudImportRequest {
  provider: CloudProvider
  credentials: CloudCredentials
  regions?: string[]
  filters?: Record<string, string[]>
  include_stopped?: boolean
  default_ssh_user?: string
  default_ssh_key?: string
  default_group_ids?: string[]
  default_tags?: string[]
  auto_verify?: boolean
}

// Import from Cloud Response
export interface CloudImportResponse {
  provider: CloudProvider
  total_discovered: number
  imported_count: number
  skipped_count: number
  failed_count: number
  imported_nodes: Array<{
    node_id: string
    name: string
    instance_id: string
    host: string
  }>
  skipped_instances: Array<{
    instance_id: string
    reason: string
  }>
  failed_instances: Array<{
    instance_id: string
    error: string
  }>
  imported_at: string
}

// Import Discovered Instances Request
export interface ImportDiscoveredRequest {
  instances: Array<{
    instance_id: string
    name?: string
    ssh_user?: string
    use_public_ip?: boolean
  }>
  default_ssh_key?: string
  default_password?: string
  credential_type?: 'ssh_key' | 'password'
  default_group_ids?: string[]
  default_tags?: string[]
  auto_verify?: boolean
}

// Import Discovered Instances Response
export interface ImportDiscoveredResponse {
  total_count: number
  imported_count: number
  failed_count: number
  imported_nodes: Array<{
    node_id: string
    name: string
    instance_id: string
    host: string
  }>
  failed_imports: Array<{
    instance_id: string
    error: string
  }>
  imported_at: string
}
