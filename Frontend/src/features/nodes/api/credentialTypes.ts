/**
 * Credentials API Types
 *
 * TypeScript interfaces for credential management.
 */

// Credential Types
export type CredentialType = 'ssh_key' | 'password' | 'winrm'

// Credential Status
export interface CredentialStatus {
  node_id: string
  node_name: string
  has_credential: boolean
  credential_type?: CredentialType
  key_version?: number
  last_rotated_at?: string
  last_verified_at?: string
  vault_stored: boolean
}

// Credential Update
export interface CredentialUpdateRequest {
  credential_type: CredentialType
  ssh_private_key?: string
  ssh_key_passphrase?: string
  password?: string
  bastion_host?: string
  bastion_port?: number
  bastion_user?: string
  bastion_ssh_key?: string
  bastion_password?: string
}

// Credential Rotation
export interface CredentialRotationRequest {
  generate_new?: boolean
  new_ssh_key?: string
  new_password?: string
  deploy_to_node?: boolean
}

export interface CredentialRotationResponse {
  node_id: string
  rotated_at: string
  credential_type: CredentialType
  deployed: boolean
  public_key?: string
}

// Bulk Rotation
export interface BulkCredentialRotationRequest {
  node_ids: string[]
  generate_new?: boolean
  deploy_to_nodes?: boolean
}

export interface BulkCredentialRotationResponse {
  total_count: number
  success_count: number
  failed_count: number
  results: Array<{
    node_id: string
    status: 'success' | 'failed'
    rotated_at?: string
    error?: string
  }>
  rotated_at: string
}

// BMC Credentials
export interface BmcCredential {
  id: string
  node_id: string
  bmc_host: string
  bmc_port: number
  bmc_protocol: 'ipmi' | 'redfish'
  bmc_user: string
  last_verified_at?: string
  is_valid?: boolean
}

export interface BmcCredentialCreateRequest {
  bmc_host: string
  bmc_port?: number
  bmc_protocol?: 'ipmi' | 'redfish'
  bmc_user: string
  password: string
}

export interface BmcCredentialUpdateRequest {
  bmc_host?: string
  bmc_port?: number
  bmc_protocol?: 'ipmi' | 'redfish'
  bmc_user?: string
  password?: string
}

// Vault Configuration
export interface VaultConfigRequest {
  vault_addr: string
  auth_method: 'token' | 'approle'
  vault_token?: string
  role_id?: string
  secret_id?: string
  namespace?: string
  mount_point?: string
}

export interface VaultStatus {
  configured: boolean
  connected: boolean
  authenticated: boolean
  vault_addr?: string
  namespace?: string
  mount_point?: string
  checked_at: string
}
