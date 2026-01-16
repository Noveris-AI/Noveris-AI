/**
 * Feature Flags Configuration
 *
 * Control feature visibility based on environment variables.
 * All feature flags are read from VITE_FEATURE_* environment variables.
 */

export const FEATURE_FLAGS = {
  // Cloud Discovery feature (AWS/Azure/GCP node discovery)
  CLOUD_DISCOVERY: import.meta.env.VITE_FEATURE_CLOUD_DISCOVERY === 'true',

  // Bulk Operations (import/export, batch actions)
  BULK_OPERATIONS: import.meta.env.VITE_FEATURE_BULK_OPERATIONS === 'true',

  // Credential Rotation (automatic credential management)
  CREDENTIAL_ROTATION: import.meta.env.VITE_FEATURE_CREDENTIAL_ROTATION === 'true',

  // Alerting System (alert rules, notifications)
  ALERTING: import.meta.env.VITE_FEATURE_ALERTING === 'true',

  // SSO Authentication
  SSO_ENABLED: import.meta.env.VITE_SSO_ENABLED === 'true',

  // WebSocket for real-time updates
  WEBSOCKET_ENABLED: import.meta.env.VITE_WS_ENABLED === 'true',
} as const

// Helper function to check if a feature is enabled
export const isFeatureEnabled = (feature: keyof typeof FEATURE_FLAGS): boolean => {
  return FEATURE_FLAGS[feature] ?? false
}

// Get all enabled features as an array
export const getEnabledFeatures = (): string[] => {
  return Object.entries(FEATURE_FLAGS)
    .filter(([, enabled]) => enabled)
    .map(([name]) => name)
}

export default FEATURE_FLAGS
