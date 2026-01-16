/**
 * Model Market API Client
 *
 * Handles all model market API calls.
 * Uses shared API configuration for consistent base URL handling.
 */

import { API_CONFIG } from '@shared/config/api'
import type {
  ModelCard,
  ModelCardDetail,
  ModelListResponse,
  ModelMarketStats,
  ModelSearchRequest,
  SyncLog,
  SyncTriggerRequest,
  SyncTriggerResponse,
  AIRecommendConfig,
  AIRecommendRequest,
  AIRecommendResponse,
} from './modelMarketTypes'

class ModelMarketClient {
  private readonly baseUrl: string

  constructor() {
    this.baseUrl = `${API_CONFIG.BASE_URL}${API_CONFIG.API_VERSION}/models`
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
      throw new Error(data.error?.message || data.message || 'Request failed')
    }

    return response.json()
  }

  // Get market statistics
  async getStats(): Promise<ModelMarketStats> {
    return this.request<ModelMarketStats>('/stats')
  }

  // Search/list models
  async searchModels(params: ModelSearchRequest): Promise<ModelListResponse> {
    const queryParams = new URLSearchParams()

    if (params.query) queryParams.append('query', params.query)
    if (params.pipeline_tag) queryParams.append('pipeline_tag', params.pipeline_tag)
    if (params.author) queryParams.append('author', params.author)
    if (params.tags) queryParams.append('tags', params.tags.join(','))
    if (params.categories) queryParams.append('categories', params.categories.join(','))
    if (params.sort_by) queryParams.append('sort_by', params.sort_by)
    if (params.sort_order) queryParams.append('sort_order', params.sort_order)
    queryParams.append('page', String(params.page ?? 1))
    queryParams.append('page_size', String(params.page_size ?? 20))

    const queryString = queryParams.toString()
    return this.request<ModelListResponse>(queryString ? `?${queryString}` : '')
  }

  // Get trending models
  async getTrendingModels(limit: number = 10): Promise<ModelCard[]> {
    return this.request<ModelCard[]>(`/trending?limit=${limit}`)
  }

  // Get recent models
  async getRecentModels(limit: number = 10): Promise<ModelCard[]> {
    return this.request<ModelCard[]>(`/recent?limit=${limit}`)
  }

  // Get model detail
  async getModelDetail(modelId: string): Promise<ModelCardDetail> {
    // URL encode the model ID since it contains '/'
    const encodedId = encodeURIComponent(modelId)
    return this.request<ModelCardDetail>(`/${encodedId}`)
  }

  // Get sync status
  async getSyncStatus(limit: number = 10): Promise<SyncLog[]> {
    return this.request<SyncLog[]>(`/sync/status?limit=${limit}`)
  }

  // Get latest sync status
  async getLatestSyncStatus(): Promise<SyncLog | null> {
    return this.request<SyncLog | null>('/sync/latest')
  }

  // Trigger sync
  async triggerSync(request: SyncTriggerRequest): Promise<SyncTriggerResponse> {
    return this.request<SyncTriggerResponse>('/sync/trigger', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Cancel sync
  async cancelSync(syncLogId: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/sync/${syncLogId}/cancel`, {
      method: 'POST',
    })
  }

  // Get pipeline tags
  async getPipelineTags(): Promise<Array<{ tag: string; name: string; count: number }>> {
    return this.request<Array<{ tag: string; name: string; count: number }>>('/pipeline-tags')
  }

  // Get categories
  async getCategories(): Promise<Array<{ category: string; count: number }>> {
    return this.request<Array<{ category: string; count: number }>>('/categories')
  }

  // Get AI config
  async getAIConfig(): Promise<AIRecommendConfig | null> {
    return this.request<AIRecommendConfig | null>('/ai-config')
  }

  // Update AI config
  async updateAIConfig(config: Partial<AIRecommendConfig> & {
    provider: string
    model_name: string
    endpoint_url: string
  }): Promise<AIRecommendConfig> {
    return this.request<AIRecommendConfig>('/ai-config', {
      method: 'POST',
      body: JSON.stringify(config),
    })
  }

  // AI recommend
  async aiRecommend(request: AIRecommendRequest): Promise<AIRecommendResponse> {
    return this.request<AIRecommendResponse>('/ai-recommend', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }
}

export const modelMarketClient = new ModelMarketClient()
