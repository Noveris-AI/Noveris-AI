/**
 * Bulk Operations API Client
 *
 * API client for bulk import, batch operations, and inventory export.
 */

import { BaseApiClient } from '@shared/lib/apiClient'
import { API_CONFIG } from '@shared/config/api'
import type {
  BulkNodeImportRequest,
  BulkNodeImportResponse,
  BulkStatusUpdateRequest,
  BulkGroupAssignRequest,
  BulkTagUpdateRequest,
  BulkDeleteRequest,
  BulkActionResponse,
  InventoryExportParams,
  CsvImportParams,
} from './bulkTypes'

class BulkOperationsClient extends BaseApiClient {
  constructor() {
    super('/bulk')
  }

  // ==========================================================================
  // Bulk Import
  // ==========================================================================

  async importNodes(data: BulkNodeImportRequest): Promise<BulkNodeImportResponse> {
    return this.post<BulkNodeImportResponse>('/import', data)
  }

  async importFromCsv(file: File, params: CsvImportParams = {}): Promise<BulkNodeImportResponse> {
    const formData = new FormData()
    formData.append('file', file)

    // Build URL with query params
    const queryParams = new URLSearchParams()
    if (params.default_ssh_key) queryParams.append('default_ssh_key', params.default_ssh_key)
    if (params.default_password) queryParams.append('default_password', params.default_password)
    if (params.auto_verify !== undefined) queryParams.append('auto_verify', String(params.auto_verify))

    const queryString = queryParams.toString()
    const url = `${API_CONFIG.BASE_URL}${API_CONFIG.API_VERSION}/bulk/import/csv${queryString ? `?${queryString}` : ''}`

    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || errorData.message || `Upload failed: ${response.status}`)
    }

    return response.json()
  }

  // ==========================================================================
  // Bulk Actions
  // ==========================================================================

  async updateStatus(data: BulkStatusUpdateRequest): Promise<BulkActionResponse> {
    return this.post<BulkActionResponse>('/status', data)
  }

  async assignGroups(data: BulkGroupAssignRequest): Promise<BulkActionResponse> {
    return this.post<BulkActionResponse>('/groups', data)
  }

  async updateTags(data: BulkTagUpdateRequest): Promise<BulkActionResponse> {
    return this.post<BulkActionResponse>('/tags', data)
  }

  async deleteNodes(data: BulkDeleteRequest): Promise<BulkActionResponse> {
    return this.post<BulkActionResponse>('/delete', data)
  }

  // ==========================================================================
  // Inventory Export
  // ==========================================================================

  async exportInventory(params: InventoryExportParams = {}): Promise<Blob> {
    const queryParams = new URLSearchParams()
    if (params.format) queryParams.append('format', params.format)
    if (params.node_ids) params.node_ids.forEach(id => queryParams.append('node_ids', id))
    if (params.group_ids) params.group_ids.forEach(id => queryParams.append('group_ids', id))
    if (params.include_vars !== undefined) queryParams.append('include_vars', String(params.include_vars))

    const queryString = queryParams.toString()
    const url = `${API_CONFIG.BASE_URL}${API_CONFIG.API_VERSION}/inventory/export${queryString ? `?${queryString}` : ''}`

    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || errorData.message || `Export failed: ${response.status}`)
    }

    return response.blob()
  }

  async downloadInventory(params: InventoryExportParams = {}): Promise<void> {
    const blob = await this.exportInventory(params)
    const format = params.format || 'yaml'
    const extension = format === 'yaml' ? 'yml' : format
    const filename = `inventory.${extension}`

    // Create download link
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  async getImportTemplate(): Promise<Blob> {
    const url = `${API_CONFIG.BASE_URL}${API_CONFIG.API_VERSION}/inventory/template`

    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error(`Failed to get template: ${response.status}`)
    }

    return response.blob()
  }

  async downloadImportTemplate(): Promise<void> {
    const blob = await this.getImportTemplate()

    // Create download link
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'node_import_template.csv'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }
}

export const bulkOperationsClient = new BulkOperationsClient()
export default bulkOperationsClient
