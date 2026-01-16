/**
 * Gateway API Client
 *
 * Provides methods for interacting with the Gateway Control Plane APIs.
 * Uses shared API configuration for consistent base URL handling.
 */

import { API_CONFIG } from '@shared/config/api'
import type {
  Upstream,
  UpstreamCreateRequest,
  UpstreamUpdateRequest,
  UpstreamListResponse,
  UpstreamTestResponse,
  VirtualModel,
  VirtualModelCreateRequest,
  VirtualModelListResponse,
  Route,
  RouteCreateRequest,
  RouteListResponse,
  DryRunRequest,
  DryRunResponse,
  APIKey,
  APIKeyCreateRequest,
  APIKeyCreateResponse,
  APIKeyListResponse,
  RequestLog,
  RequestLogListResponse,
  RequestLogSearchParams,
  GatewayOverview,
} from './gatewayTypes'

class GatewayClient {
  private readonly baseUrl: string

  constructor() {
    this.baseUrl = API_CONFIG.BASE_URL
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
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

    if (response.status === 204) {
      return {} as T
    }

    return response.json()
  }

  // ===========================================================================
  // Upstreams
  // ===========================================================================

  async listUpstreams(params: {
    page?: number
    page_size?: number
    type?: string
    enabled?: boolean
    search?: string
  } = {}): Promise<UpstreamListResponse> {
    const queryParams = new URLSearchParams()
    if (params.page) queryParams.append('page', String(params.page))
    if (params.page_size) queryParams.append('page_size', String(params.page_size))
    if (params.type) queryParams.append('type', params.type)
    if (params.enabled !== undefined) queryParams.append('enabled', String(params.enabled))
    if (params.search) queryParams.append('search', params.search)

    const qs = queryParams.toString()
    return this.request<UpstreamListResponse>(`/api/gateway/upstreams${qs ? `?${qs}` : ''}`)
  }

  async getUpstream(id: string): Promise<Upstream> {
    return this.request<Upstream>(`/api/gateway/upstreams/${id}`)
  }

  async createUpstream(data: UpstreamCreateRequest): Promise<Upstream> {
    return this.request<Upstream>('/api/gateway/upstreams', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateUpstream(id: string, data: UpstreamUpdateRequest): Promise<Upstream> {
    return this.request<Upstream>(`/api/gateway/upstreams/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteUpstream(id: string): Promise<void> {
    await this.request<void>(`/api/gateway/upstreams/${id}`, { method: 'DELETE' })
  }

  async testUpstream(id: string): Promise<UpstreamTestResponse> {
    return this.request<UpstreamTestResponse>(`/api/gateway/upstreams/${id}/test`, {
      method: 'POST',
    })
  }

  // ===========================================================================
  // Virtual Models
  // ===========================================================================

  async listVirtualModels(params: {
    page?: number
    page_size?: number
    enabled?: boolean
    search?: string
  } = {}): Promise<VirtualModelListResponse> {
    const queryParams = new URLSearchParams()
    if (params.page) queryParams.append('page', String(params.page))
    if (params.page_size) queryParams.append('page_size', String(params.page_size))
    if (params.enabled !== undefined) queryParams.append('enabled', String(params.enabled))
    if (params.search) queryParams.append('search', params.search)

    const qs = queryParams.toString()
    return this.request<VirtualModelListResponse>(`/api/gateway/virtual-models${qs ? `?${qs}` : ''}`)
  }

  async getVirtualModel(id: string): Promise<VirtualModel> {
    return this.request<VirtualModel>(`/api/gateway/virtual-models/${id}`)
  }

  async createVirtualModel(data: VirtualModelCreateRequest): Promise<VirtualModel> {
    return this.request<VirtualModel>('/api/gateway/virtual-models', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateVirtualModel(id: string, data: Partial<VirtualModelCreateRequest>): Promise<VirtualModel> {
    return this.request<VirtualModel>(`/api/gateway/virtual-models/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteVirtualModel(id: string): Promise<void> {
    await this.request<void>(`/api/gateway/virtual-models/${id}`, { method: 'DELETE' })
  }

  // ===========================================================================
  // Routes
  // ===========================================================================

  async listRoutes(params: {
    page?: number
    page_size?: number
    enabled?: boolean
  } = {}): Promise<RouteListResponse> {
    const queryParams = new URLSearchParams()
    if (params.page) queryParams.append('page', String(params.page))
    if (params.page_size) queryParams.append('page_size', String(params.page_size))
    if (params.enabled !== undefined) queryParams.append('enabled', String(params.enabled))

    const qs = queryParams.toString()
    return this.request<RouteListResponse>(`/api/gateway/routes${qs ? `?${qs}` : ''}`)
  }

  async getRoute(id: string): Promise<Route> {
    return this.request<Route>(`/api/gateway/routes/${id}`)
  }

  async createRoute(data: RouteCreateRequest): Promise<Route> {
    return this.request<Route>('/api/gateway/routes', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateRoute(id: string, data: Partial<RouteCreateRequest>): Promise<Route> {
    return this.request<Route>(`/api/gateway/routes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteRoute(id: string): Promise<void> {
    await this.request<void>(`/api/gateway/routes/${id}`, { method: 'DELETE' })
  }

  async dryRunRoute(data: DryRunRequest): Promise<DryRunResponse> {
    return this.request<DryRunResponse>('/api/gateway/routes/dry-run', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // ===========================================================================
  // API Keys
  // ===========================================================================

  async listAPIKeys(params: {
    page?: number
    page_size?: number
    enabled?: boolean
    search?: string
  } = {}): Promise<APIKeyListResponse> {
    const queryParams = new URLSearchParams()
    if (params.page) queryParams.append('page', String(params.page))
    if (params.page_size) queryParams.append('page_size', String(params.page_size))
    if (params.enabled !== undefined) queryParams.append('enabled', String(params.enabled))
    if (params.search) queryParams.append('search', params.search)

    const qs = queryParams.toString()
    return this.request<APIKeyListResponse>(`/api/gateway/api-keys${qs ? `?${qs}` : ''}`)
  }

  async getAPIKey(id: string): Promise<APIKey> {
    return this.request<APIKey>(`/api/gateway/api-keys/${id}`)
  }

  async createAPIKey(data: APIKeyCreateRequest): Promise<APIKeyCreateResponse> {
    return this.request<APIKeyCreateResponse>('/api/gateway/api-keys', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateAPIKey(id: string, data: Partial<APIKeyCreateRequest>): Promise<APIKey> {
    return this.request<APIKey>(`/api/gateway/api-keys/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteAPIKey(id: string): Promise<void> {
    await this.request<void>(`/api/gateway/api-keys/${id}`, { method: 'DELETE' })
  }

  async regenerateAPIKey(id: string): Promise<APIKeyCreateResponse> {
    return this.request<APIKeyCreateResponse>(`/api/gateway/api-keys/${id}/regenerate`, {
      method: 'POST',
    })
  }

  // ===========================================================================
  // Request Logs
  // ===========================================================================

  async listRequestLogs(params: RequestLogSearchParams = {}): Promise<RequestLogListResponse> {
    const queryParams = new URLSearchParams()
    if (params.page) queryParams.append('page', String(params.page))
    if (params.page_size) queryParams.append('page_size', String(params.page_size))
    if (params.request_id) queryParams.append('request_id', params.request_id)
    if (params.api_key_id) queryParams.append('api_key_id', params.api_key_id)
    if (params.endpoint) queryParams.append('endpoint', params.endpoint)
    if (params.virtual_model) queryParams.append('virtual_model', params.virtual_model)
    if (params.upstream_id) queryParams.append('upstream_id', params.upstream_id)
    if (params.status_code) queryParams.append('status_code', String(params.status_code))
    if (params.error_type) queryParams.append('error_type', params.error_type)
    if (params.start_date) queryParams.append('start_date', params.start_date)
    if (params.end_date) queryParams.append('end_date', params.end_date)

    const qs = queryParams.toString()
    return this.request<RequestLogListResponse>(`/api/gateway/requests${qs ? `?${qs}` : ''}`)
  }

  async getRequestLog(id: string): Promise<RequestLog> {
    return this.request<RequestLog>(`/api/gateway/requests/${id}`)
  }

  // ===========================================================================
  // Overview / Stats
  // ===========================================================================

  async getOverview(params: {
    start_date?: string
    end_date?: string
  } = {}): Promise<GatewayOverview> {
    const queryParams = new URLSearchParams()
    if (params.start_date) queryParams.append('start_date', params.start_date)
    if (params.end_date) queryParams.append('end_date', params.end_date)

    const qs = queryParams.toString()
    return this.request<GatewayOverview>(`/api/gateway/overview${qs ? `?${qs}` : ''}`)
  }
}

export const gatewayClient = new GatewayClient()
export default gatewayClient
