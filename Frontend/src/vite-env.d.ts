/// <reference types="vite/client" />

interface ImportMetaEnv {
  // API Configuration
  readonly VITE_API_BASE_URL?: string

  // Authentication
  readonly VITE_AUTH_API_MODE?: 'mock' | 'real'
  readonly VITE_AUTH_REDIRECT_AFTER_LOGIN?: string
  readonly VITE_SSO_ENABLED?: string

  // Application Info
  readonly VITE_APP_NAME?: string
  readonly VITE_APP_VERSION?: string

  // Feature Flags
  readonly VITE_FEATURE_CLOUD_DISCOVERY?: string
  readonly VITE_FEATURE_BULK_OPERATIONS?: string
  readonly VITE_FEATURE_CREDENTIAL_ROTATION?: string
  readonly VITE_FEATURE_ALERTING?: string

  // UI Configuration
  readonly VITE_DEFAULT_THEME?: 'light' | 'dark' | 'system'
  readonly VITE_DEFAULT_LANGUAGE?: string

  // Polling Intervals (milliseconds)
  readonly VITE_POLLING_INTERVAL_DASHBOARD?: string
  readonly VITE_POLLING_INTERVAL_JOBS?: string
  readonly VITE_POLLING_INTERVAL_ALERTS?: string
  readonly VITE_POLLING_INTERVAL_NODES?: string

  // WebSocket Configuration
  readonly VITE_WS_ENABLED?: string
  readonly VITE_WS_RECONNECT_INTERVAL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
