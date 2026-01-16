/**
 * API Configuration
 *
 * Centralized configuration for all API clients.
 * All values are read from environment variables to avoid hardcoding.
 */

// API Base URL - read from environment, no hardcoded fallback in production
const getApiBaseUrl = (): string => {
  const url = import.meta.env.VITE_API_BASE_URL
  if (!url) {
    // Only provide fallback in development mode
    if (import.meta.env.DEV) {
      console.warn('VITE_API_BASE_URL not set, using localhost:8000 for development')
      return 'http://localhost:8000'
    }
    throw new Error('VITE_API_BASE_URL environment variable is required')
  }
  return url
}

export const API_CONFIG = {
  // Base URL for all API requests
  BASE_URL: getApiBaseUrl(),

  // API version prefix
  API_VERSION: '/api/v1',

  // Request timeout (milliseconds)
  TIMEOUT: 30000,

  // Retry configuration
  RETRY: {
    MAX_RETRIES: 3,
    RETRY_DELAY: 1000, // Base delay in ms
    RETRY_MULTIPLIER: 2, // Exponential backoff multiplier
  },

  // Endpoints configuration
  ENDPOINTS: {
    // Node Management
    NODES: '/nodes',
    NODE_GROUPS: '/node-groups',
    JOB_TEMPLATES: '/job-templates',
    JOB_RUNS: '/job-runs',
    GROUP_VARS: '/group-vars',
    STATS: '/stats',

    // Alerting
    ALERTS: '/alerts',
    ALERT_RULES: '/alerts/rules',
    NOTIFICATION_CHANNELS: '/alerts/channels',

    // Credentials
    CREDENTIALS: '/credentials',

    // Bulk Operations
    BULK: '/bulk',
    INVENTORY: '/inventory',

    // Cloud Discovery
    CLOUD: '/cloud',

    // Auth
    AUTH: '/auth',

    // Monitoring
    MONITORING: '/monitoring',

    // Gateway
    GATEWAY: '/gateway',

    // Settings
    SETTINGS: '/settings',

    // Authorization
    AUTHZ: '/authz',
  },
} as const

// Build full URL helper
export const buildApiUrl = (endpoint: string, params?: Record<string, string>): string => {
  let url = `${API_CONFIG.BASE_URL}${API_CONFIG.API_VERSION}${endpoint}`

  if (params) {
    const searchParams = new URLSearchParams(params)
    const queryString = searchParams.toString()
    if (queryString) {
      url += `?${queryString}`
    }
  }

  return url
}

// WebSocket URL helper
export const buildWsUrl = (endpoint: string): string => {
  const baseUrl = API_CONFIG.BASE_URL
  const wsProtocol = baseUrl.startsWith('https') ? 'wss' : 'ws'
  const wsBase = baseUrl.replace(/^https?/, wsProtocol)
  return `${wsBase}${API_CONFIG.API_VERSION}${endpoint}`
}

export default API_CONFIG
