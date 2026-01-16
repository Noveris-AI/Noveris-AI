/**
 * Polling Configuration
 *
 * Centralized polling intervals for real-time data updates.
 * All values are read from environment variables with sensible defaults.
 */

const parseInterval = (envValue: string | undefined, defaultValue: number): number => {
  if (!envValue) return defaultValue
  const parsed = parseInt(envValue, 10)
  return isNaN(parsed) ? defaultValue : parsed
}

export const POLLING_CONFIG = {
  // Dashboard overview polling (default: 30s)
  DASHBOARD: parseInterval(import.meta.env.VITE_POLLING_INTERVAL_DASHBOARD, 30000),

  // Job status polling (default: 3s for active jobs)
  JOBS: parseInterval(import.meta.env.VITE_POLLING_INTERVAL_JOBS, 3000),

  // Alert status polling (default: 10s)
  ALERTS: parseInterval(import.meta.env.VITE_POLLING_INTERVAL_ALERTS, 10000),

  // Node status polling (default: 15s)
  NODES: parseInterval(import.meta.env.VITE_POLLING_INTERVAL_NODES, 15000),

  // Deployment status polling (default: 5s)
  DEPLOYMENTS: 5000,

  // Model market sync status (default: 5s)
  MODEL_MARKET: 5000,

  // Monitoring overview (default: 30s)
  MONITORING: 30000,

  // WebSocket reconnect interval
  WS_RECONNECT: parseInterval(import.meta.env.VITE_WS_RECONNECT_INTERVAL, 5000),
} as const

export default POLLING_CONFIG
