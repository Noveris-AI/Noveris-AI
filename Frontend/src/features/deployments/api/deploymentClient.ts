/**
 * Model Deployment API Client
 *
 * Handles all deployment-related API calls.
 * Uses shared API configuration for consistent base URL handling.
 */

import { API_CONFIG } from '@shared/config/api'
import type {
  Deployment,
  DeploymentDetail,
  DeploymentListResponse,
  DeploymentCreateRequest,
  DeploymentUpdateRequest,
  DeploymentSearchParams,
  DeploymentActionResponse,
  DeploymentHealthResponse,
  CompatibilityCheckRequest,
  CompatibilityCheckResult,
  NodeAccelerators,
  LogStreamResponse,
  DeploymentLogListResponse,
  FrameworkConfigTemplate,
} from './deploymentTypes'

class DeploymentClient {
  private readonly baseUrl: string

  constructor() {
    this.baseUrl = `${API_CONFIG.BASE_URL}${API_CONFIG.API_VERSION}`
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      credentials: 'include',
    })

    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || data.message || `Request failed: ${response.status}`)
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T
    }

    return response.json()
  }

  // ==========================================================================
  // Deployments CRUD
  // ==========================================================================

  async listDeployments(params: DeploymentSearchParams = {}): Promise<DeploymentListResponse> {
    const queryParams = new URLSearchParams()

    if (params.page) queryParams.append('page', String(params.page))
    if (params.page_size) queryParams.append('page_size', String(params.page_size))
    if (params.search) queryParams.append('search', params.search)
    if (params.framework) queryParams.append('framework', params.framework)
    if (params.status) queryParams.append('status', params.status)
    if (params.node_id) queryParams.append('node_id', params.node_id)
    if (params.tags?.length) {
      params.tags.forEach(tag => queryParams.append('tags', tag))
    }

    const queryString = queryParams.toString()
    return this.request<DeploymentListResponse>(`/deployments${queryString ? `?${queryString}` : ''}`)
  }

  async getDeployment(deploymentId: string): Promise<DeploymentDetail> {
    return this.request<DeploymentDetail>(`/deployments/${deploymentId}`)
  }

  async createDeployment(data: DeploymentCreateRequest): Promise<Deployment> {
    return this.request<Deployment>('/deployments', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateDeployment(deploymentId: string, data: DeploymentUpdateRequest): Promise<Deployment> {
    return this.request<Deployment>(`/deployments/${deploymentId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteDeployment(deploymentId: string): Promise<void> {
    await this.request<void>(`/deployments/${deploymentId}`, {
      method: 'DELETE',
    })
  }

  // ==========================================================================
  // Deployment Actions
  // ==========================================================================

  async startDeployment(deploymentId: string): Promise<DeploymentActionResponse> {
    return this.request<DeploymentActionResponse>(`/deployments/${deploymentId}/start`, {
      method: 'POST',
    })
  }

  async stopDeployment(deploymentId: string): Promise<DeploymentActionResponse> {
    return this.request<DeploymentActionResponse>(`/deployments/${deploymentId}/stop`, {
      method: 'POST',
    })
  }

  async restartDeployment(deploymentId: string): Promise<DeploymentActionResponse> {
    return this.request<DeploymentActionResponse>(`/deployments/${deploymentId}/restart`, {
      method: 'POST',
    })
  }

  // ==========================================================================
  // Health & Logs
  // ==========================================================================

  async checkDeploymentHealth(deploymentId: string): Promise<DeploymentHealthResponse> {
    return this.request<DeploymentHealthResponse>(`/deployments/${deploymentId}/health`)
  }

  async getDeploymentLogs(
    deploymentId: string,
    params: { page?: number; page_size?: number; level?: string } = {}
  ): Promise<DeploymentLogListResponse> {
    const queryParams = new URLSearchParams()
    if (params.page) queryParams.append('page', String(params.page))
    if (params.page_size) queryParams.append('page_size', String(params.page_size))
    if (params.level) queryParams.append('level', params.level)

    const queryString = queryParams.toString()
    return this.request<DeploymentLogListResponse>(
      `/deployments/${deploymentId}/logs${queryString ? `?${queryString}` : ''}`
    )
  }

  async getServiceLogs(
    deploymentId: string,
    params: { lines?: number; source?: 'stdout' | 'stderr' | 'all' } = {}
  ): Promise<LogStreamResponse> {
    const queryParams = new URLSearchParams()
    if (params.lines) queryParams.append('lines', String(params.lines))
    if (params.source) queryParams.append('source', params.source)

    const queryString = queryParams.toString()
    return this.request<LogStreamResponse>(
      `/deployments/${deploymentId}/service-logs${queryString ? `?${queryString}` : ''}`
    )
  }

  // ==========================================================================
  // Compatibility & Node Info
  // ==========================================================================

  async checkCompatibility(data: CompatibilityCheckRequest): Promise<CompatibilityCheckResult> {
    return this.request<CompatibilityCheckResult>('/deployments/compatibility', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getNodeAccelerators(nodeId: string): Promise<NodeAccelerators> {
    return this.request<NodeAccelerators>(`/deployments/nodes/${nodeId}/accelerators`)
  }

  // ==========================================================================
  // Configuration Templates
  // ==========================================================================

  async getFrameworkTemplates(): Promise<{ templates: FrameworkConfigTemplate[] }> {
    return this.request<{ templates: FrameworkConfigTemplate[] }>('/deployments/templates')
  }
}

export const deploymentClient = new DeploymentClient()
