/**
 * Credentials API Client
 *
 * API client for credential management operations.
 */

import { BaseApiClient } from '@shared/lib/apiClient'
import type {
  CredentialStatus,
  CredentialUpdateRequest,
  CredentialRotationRequest,
  CredentialRotationResponse,
  BulkCredentialRotationRequest,
  BulkCredentialRotationResponse,
  BmcCredential,
  BmcCredentialCreateRequest,
  BmcCredentialUpdateRequest,
  VaultConfigRequest,
  VaultStatus,
} from './credentialTypes'

class CredentialClient extends BaseApiClient {
  constructor() {
    super('/credentials')
  }

  // ==========================================================================
  // Node Credentials
  // ==========================================================================

  async getCredentialStatus(nodeId: string): Promise<CredentialStatus> {
    return this.get<CredentialStatus>(`/nodes/${nodeId}`)
  }

  async getBulkCredentialStatus(nodeIds: string[]): Promise<{
    total_count: number
    results: Array<CredentialStatus & { status: string; error?: string }>
    checked_at: string
  }> {
    const params = { node_ids: nodeIds.join(',') }
    return this.get('/bulk-status', params)
  }

  async updateCredential(nodeId: string, data: CredentialUpdateRequest): Promise<{
    node_id: string
    credential_type: string
    updated_at: string
    updated_by: string
  }> {
    return this.put(`/nodes/${nodeId}`, data)
  }

  async rotateCredential(nodeId: string, data: CredentialRotationRequest = {}): Promise<CredentialRotationResponse> {
    return this.post<CredentialRotationResponse>(`/nodes/${nodeId}:rotate`, data)
  }

  async bulkRotateCredentials(data: BulkCredentialRotationRequest): Promise<BulkCredentialRotationResponse> {
    return this.post<BulkCredentialRotationResponse>(':rotate-bulk', data)
  }

  // ==========================================================================
  // BMC Credentials
  // ==========================================================================

  async getBmcCredential(nodeId: string): Promise<BmcCredential> {
    return this.get<BmcCredential>(`/nodes/${nodeId}/bmc`)
  }

  async createBmcCredential(nodeId: string, data: BmcCredentialCreateRequest): Promise<BmcCredential> {
    return this.post<BmcCredential>(`/nodes/${nodeId}/bmc`, data)
  }

  async updateBmcCredential(nodeId: string, data: BmcCredentialUpdateRequest): Promise<BmcCredential> {
    return this.put<BmcCredential>(`/nodes/${nodeId}/bmc`, data)
  }

  async deleteBmcCredential(nodeId: string): Promise<void> {
    await this.delete<void>(`/nodes/${nodeId}/bmc`)
  }

  async verifyBmcCredential(nodeId: string): Promise<{
    node_id: string
    is_valid: boolean
    verified_at: string
    error?: string
  }> {
    return this.post(`/nodes/${nodeId}/bmc:verify`, {})
  }

  // ==========================================================================
  // Vault Integration
  // ==========================================================================

  async configureVault(data: VaultConfigRequest): Promise<{
    configured: boolean
    vault_addr: string
    namespace?: string
    mount_point: string
    configured_at: string
  }> {
    return this.post('/vault/configure', data)
  }

  async getVaultStatus(): Promise<VaultStatus> {
    return this.get<VaultStatus>('/vault/status')
  }

  async migrateToVault(nodeIds?: string[], allNodes: boolean = false): Promise<{
    status: string
    message: string
    migrated_count?: number
  }> {
    const params: Record<string, string | boolean | undefined> = {}
    if (nodeIds) params.node_ids = nodeIds.join(',')
    if (allNodes) params.all_nodes = allNodes

    return this.post('/vault/migrate', {}, params)
  }
}

export const credentialClient = new CredentialClient()
export default credentialClient
