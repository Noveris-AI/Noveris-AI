/**
 * Model Market API Types
 */

// Pipeline tags for filtering
export type PipelineTag =
  | 'text-generation'
  | 'text2text-generation'
  | 'fill-mask'
  | 'token-classification'
  | 'text-classification'
  | 'question-answering'
  | 'summarization'
  | 'translation'
  | 'sentence-similarity'
  | 'feature-extraction'
  | 'rerank'
  | 'text-to-speech'
  | 'automatic-speech-recognition'
  | 'image-classification'
  | 'object-detection'
  | 'image-segmentation'
  | 'text-to-image'
  | 'image-to-image'
  | 'zero-shot-classification'
  | 'zero-shot-image-classification'
  | 'reinforcement-learning'
  | 'robotics'
  | 'tabular-classification'
  | 'tabular-regression'
  | 'audio-classification'
  | 'audio-to-audio'

// Sort options
export type SortBy = 'last_modified' | 'downloads' | 'likes' | 'model_name' | 'author'
export type SortOrder = 'asc' | 'desc'

// Sync status
export type SyncStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type SyncType = 'full' | 'incremental'
export type SyncSource = 'huggingface' | 'hf-mirror'

// Model card (brief)
export interface ModelCard {
  model_id: string
  model_name: string
  author: string | null
  description: string | null
  pipeline_tag: PipelineTag | null
  downloads: number
  likes: number
  last_modified: string
}

// Model card detail
export interface ModelCardDetail extends ModelCard {
  sha: string | null
  created_at: string | null
  tags: string[] | null
  library_name: string | null
  card_data: Record<string, any> | null
  config: Record<string, any> | null
  indexed_tags: string[] | null
  indexed_categories: string[] | null
  source: string
  source_url: string
  synced_at: string
}

// Category stats
export interface CategoryStats {
  category: string
  count: number
}

// Pipeline tag stats
export interface PipelineTagStats {
  tag: string
  display_name: string
  count: number
}

// Market stats
export interface ModelMarketStats {
  total_models: number
  total_authors: number
  pipeline_tags: PipelineTagStats[]
  categories: CategoryStats[]
  last_sync: string | null
  sync_status: SyncStatus | null
}

// Model list response
export interface ModelListResponse {
  total: number
  page: number
  page_size: number
  total_pages: number
  models: ModelCard[]
}

// Model search request
export interface ModelSearchRequest {
  query?: string
  pipeline_tag?: PipelineTag
  author?: string
  tags?: string[]
  categories?: string[]
  sort_by?: SortBy
  sort_order?: SortOrder
  page?: number
  page_size?: number
}

// Sync log
export interface SyncLog {
  id: number
  sync_type: SyncType
  status: SyncStatus
  started_at: string | null
  completed_at: string | null
  total_models: number | null
  synced_models: number
  updated_models: number
  failed_models: number
  skipped_models: number
  current_page: number
  total_pages: number
  progress_percentage: number
  error_message: string | null
  source: SyncSource
  triggered_by: string
}

// Sync trigger request
export interface SyncTriggerRequest {
  sync_type: SyncType
  source?: SyncSource
}

// Sync trigger response
export interface SyncTriggerResponse {
  sync_log_id: number
  message: string
  sync_type: SyncType
  status: SyncStatus
}

// AI recommendation config
export interface AIRecommendConfig {
  id: number
  is_active: boolean
  provider: string
  model_name: string
  endpoint_url: string
  api_key: string | null
  api_key_required: boolean
  temperature: number
  max_tokens: number
  system_prompt: string | null
  created_at: string
  updated_at: string | null
}

// AI recommend request
export interface AIRecommendRequest {
  query: string
  max_results?: number
}

// AI recommend model
export interface AIRecommendModel {
  model_id: string
  model_name: string
  author: string | null
  description: string | null
  pipeline_tag: PipelineTag | null
  downloads: number
  likes: number
  reason: string
}

// AI recommend response
export interface AIRecommendResponse {
  recommendations: AIRecommendModel[]
  query: string
  total_found: number
}

// Common API response wrapper
export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: {
    code: string | number
    message: string
  }
}
