/**
 * Gateway API Types
 */

// =============================================================================
// Enums
// =============================================================================

export type UpstreamType =
  | 'openai'
  | 'openai_compatible'
  | 'anthropic'
  | 'gemini'
  | 'cohere'
  | 'stable_diffusion'
  | 'custom_http'

export type AuthType = 'bearer' | 'header' | 'query' | 'none'

export type LogPayloadMode = 'none' | 'metadata_only' | 'sampled' | 'full_with_redaction'

export type Capability =
  | 'chat_completions'
  | 'completions'
  | 'responses'
  | 'embeddings'
  | 'images_generations'
  | 'images_edits'
  | 'images_variations'
  | 'audio_speech'
  | 'audio_transcriptions'
  | 'audio_translations'
  | 'moderations'
  | 'rerank'

// =============================================================================
// Upstreams
// =============================================================================

export interface Upstream {
  id: string
  name: string
  description?: string
  type: UpstreamType
  base_url: string
  auth_type: AuthType
  has_credentials: boolean
  allow_hosts: string[]
  allow_cidrs: string[]
  supported_capabilities: Capability[]
  model_mapping: Record<string, string>
  healthcheck: {
    path?: string
    method?: string
    interval_seconds?: number
    timeout_seconds?: number
    expected_status?: number
  }
  timeout_ms: number
  max_retries: number
  circuit_breaker: {
    failure_threshold?: number
    success_threshold?: number
    timeout_seconds?: number
    half_open_max_requests?: number
  }
  health_status: 'healthy' | 'unhealthy' | 'unknown'
  last_health_check_at?: string
  health_check_error?: string
  deployment_id?: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface UpstreamCreateRequest {
  name: string
  description?: string
  type: UpstreamType
  base_url: string
  auth_type?: AuthType
  credentials?: string
  allow_hosts?: string[]
  allow_cidrs?: string[]
  supported_capabilities?: Capability[]
  model_mapping?: Record<string, string>
  healthcheck?: Upstream['healthcheck']
  timeout_ms?: number
  max_retries?: number
  circuit_breaker?: Upstream['circuit_breaker']
  deployment_id?: string
  enabled?: boolean
}

export interface UpstreamUpdateRequest {
  name?: string
  description?: string
  base_url?: string
  auth_type?: AuthType
  credentials?: string
  allow_hosts?: string[]
  allow_cidrs?: string[]
  supported_capabilities?: Capability[]
  model_mapping?: Record<string, string>
  healthcheck?: Upstream['healthcheck']
  timeout_ms?: number
  max_retries?: number
  circuit_breaker?: Upstream['circuit_breaker']
  deployment_id?: string
  enabled?: boolean
}

export interface UpstreamListResponse {
  items: Upstream[]
  total: number
  page: number
  page_size: number
}

export interface UpstreamTestResponse {
  success: boolean
  latency_ms?: number
  error?: string
  capabilities_detected: Capability[]
}

// =============================================================================
// Virtual Models
// =============================================================================

export interface VirtualModel {
  id: string
  name: string
  display_name?: string
  description?: string
  capabilities: Capability[]
  tags: Record<string, string>
  default_route_id?: string
  metadata: Record<string, unknown>
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface VirtualModelCreateRequest {
  name: string
  display_name?: string
  description?: string
  capabilities?: Capability[]
  tags?: Record<string, string>
  default_route_id?: string
  metadata?: Record<string, unknown>
  enabled?: boolean
}

export interface VirtualModelListResponse {
  items: VirtualModel[]
  total: number
  page: number
  page_size: number
}

// =============================================================================
// Routes
// =============================================================================

export interface WeightedUpstream {
  upstream_id: string
  weight: number
}

export interface RouteMatch {
  endpoint?: string
  virtual_model?: string
  tenant_id?: string
  api_key_id?: string
  tags?: Record<string, string>
}

export interface RouteAction {
  primary_upstreams: WeightedUpstream[]
  fallback_upstreams?: string[]
  retry_policy?: {
    max_retries: number
    retry_on_status: number[]
    backoff_ms: number
    backoff_multiplier: number
  }
  cache_policy?: {
    enabled: boolean
    ttl_seconds: number
  }
  request_transform?: {
    inject_headers?: Record<string, string>
    model_override?: string
  }
  timeout_ms_override?: number
}

export interface Route {
  id: string
  name: string
  description?: string
  priority: number
  match: RouteMatch
  action: RouteAction
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface RouteCreateRequest {
  name: string
  description?: string
  priority?: number
  match: RouteMatch
  action: RouteAction
  enabled?: boolean
}

export interface RouteListResponse {
  items: Route[]
  total: number
  page: number
  page_size: number
}

export interface DryRunRequest {
  endpoint: string
  virtual_model: string
  tags?: Record<string, string>
}

export interface DryRunResponse {
  context: {
    endpoint: string
    virtual_model: string
    tenant_id: string
    api_key_id?: string
    tags: Record<string, string>
  }
  evaluated_routes: {
    route_id: string
    route_name: string
    priority: number
    enabled: boolean
    matches: boolean
    reason: string
  }[]
  selected_route?: {
    route_id: string
    route_name: string
  }
  selected_upstream?: {
    upstream_id: string
    upstream_name: string
    upstream_type: string
    upstream_model: string
    is_fallback: boolean
    selection_reason: string
  }
  error?: string
}

// =============================================================================
// API Keys
// =============================================================================

export interface APIKey {
  id: string
  name: string
  description?: string
  key_prefix: string
  allowed_models: string[]
  allowed_endpoints: string[]
  rate_limit: {
    requests_per_minute?: number
    requests_per_hour?: number
    requests_per_day?: number
    tokens_per_minute?: number
    tokens_per_day?: number
  }
  quota: {
    max_tokens?: number
    max_requests?: number
    reset_interval?: 'daily' | 'weekly' | 'monthly' | 'never'
    current_tokens_used?: number
    current_requests_used?: number
    quota_reset_at?: string
  }
  log_payload_mode: LogPayloadMode
  expires_at?: string
  enabled: boolean
  last_used_at?: string
  created_at: string
  updated_at: string
}

export interface APIKeyCreateRequest {
  name: string
  description?: string
  allowed_models?: string[]
  allowed_endpoints?: string[]
  rate_limit?: APIKey['rate_limit']
  quota?: APIKey['quota']
  log_payload_mode?: LogPayloadMode
  expires_at?: string
  enabled?: boolean
}

export interface APIKeyCreateResponse {
  id: string
  name: string
  key: string // Full key, shown only once
  key_prefix: string
  created_at: string
}

export interface APIKeyListResponse {
  items: APIKey[]
  total: number
  page: number
  page_size: number
}

// =============================================================================
// Request Logs
// =============================================================================

export interface RequestLog {
  id: string
  request_id: string
  trace_id?: string
  api_key_id?: string
  endpoint: string
  method: string
  virtual_model?: string
  upstream_id?: string
  upstream_model?: string
  status_code?: number
  error_type?: string
  error_message?: string
  latency_ms?: number
  upstream_latency_ms?: number
  time_to_first_token_ms?: number
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  cost_usd?: number
  estimated_cost?: boolean
  request_meta: Record<string, unknown>
  response_meta: Record<string, unknown>
  created_at: string
}

export interface RequestLogListResponse {
  items: RequestLog[]
  total: number
  page: number
  page_size: number
}

export interface RequestLogSearchParams {
  page?: number
  page_size?: number
  request_id?: string
  api_key_id?: string
  endpoint?: string
  virtual_model?: string
  upstream_id?: string
  status_code?: number
  error_type?: string
  start_date?: string
  end_date?: string
}

// =============================================================================
// Overview / Stats
// =============================================================================

export interface GatewayOverview {
  total_requests: number
  total_errors: number
  error_rate: number
  avg_latency_ms: number
  p95_latency_ms: number
  total_tokens: number
  total_cost_usd: number
  top_models: { model: string; count: number }[]
  top_upstreams: { upstream: string; count: number }[]
  requests_by_hour: { hour: string; count: number }[]
}
