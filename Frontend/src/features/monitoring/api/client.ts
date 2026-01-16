/**
 * Monitoring API Client
 *
 * HTTP client for monitoring endpoints.
 * Uses shared API configuration for consistent base URL handling.
 */

import { BaseApiClient } from '@shared/lib/apiClient'

// Types
export interface KeyMetric {
  name: string
  value: number | string
  unit?: string
  status: 'ok' | 'warning' | 'critical' | 'unknown'
  change_percent?: number
}

export interface SparklineData {
  points: number[][]
  trend?: 'up' | 'down' | 'stable'
}

export interface HelpTooltip {
  description: string
  causes: string[]
  actions: string[]
}

export interface OverviewCard {
  key: string
  title_i18n_key: string
  description_i18n_key?: string
  status: 'ok' | 'warning' | 'critical' | 'unknown'
  key_metrics: KeyMetric[]
  sparkline?: SparklineData
  help_tooltip?: HelpTooltip
  route: string
}

export interface OverviewResponse {
  cards: OverviewCard[]
  last_updated: string
  data_sources_status: Record<string, string>
}

export interface NodeSummary {
  instance: string
  hostname: string
  status: string
  labels: Record<string, string>
}

export interface AcceleratorSummary {
  vendor: string
  device_id: string
  model: string
  hostname: string
  uuid?: string
  temperature?: number
}

export interface MonitoringSettings {
  prometheus_url: string
  prometheus_enabled: boolean
  loki_url: string
  loki_enabled: boolean
  tempo_url: string
  tempo_enabled: boolean
  alertmanager_url: string
  alertmanager_enabled: boolean
  enabled_domains: Record<string, boolean>
  default_range: string
  default_mode: string
}

export interface MonitoringTarget {
  id: string
  type: string
  endpoint: string
  labels: Record<string, string>
  status: string
}

export interface MonitoringEvent {
  id: string
  type: string
  level: string
  message: string
  timestamp: string
  labels: Record<string, string>
}

export interface CostSummary {
  total_cost: number
  currency: string
  period: string
  breakdown: Record<string, number>
}

export interface Budget {
  id: string
  name: string
  amount: number
  currency: string
  period: string
  spent: number
  remaining: number
}

export interface Adapter {
  id: string
  name: string
  type: string
  status: string
  config: Record<string, unknown>
}

// Monitoring API Client
class MonitoringClient extends BaseApiClient {
  constructor() {
    super('/monitoring')
  }

  // Overview
  async getOverview(range = '1h'): Promise<OverviewResponse> {
    return this.get<OverviewResponse>('/overview', { range })
  }

  async getDataSourcesHealth(): Promise<Record<string, string>> {
    return this.get<Record<string, string>>('/overview/health')
  }

  // Nodes
  async getNodes(): Promise<{ nodes: NodeSummary[] }> {
    return this.get<{ nodes: NodeSummary[] }>('/nodes')
  }

  async getNodeMetrics(nodeId: string, range = '1h'): Promise<Record<string, unknown>> {
    return this.get<Record<string, unknown>>(`/nodes/${nodeId}/metrics`, { range })
  }

  // Accelerators
  async getAccelerators(): Promise<{ accelerators: AcceleratorSummary[] }> {
    return this.get<{ accelerators: AcceleratorSummary[] }>('/accelerators')
  }

  async getAcceleratorMetrics(
    nodeId: string,
    device: string,
    range = '1h'
  ): Promise<Record<string, unknown>> {
    return this.get<Record<string, unknown>>(`/accelerators/${nodeId}/metrics`, { device, range })
  }

  // Gateway
  async getGatewayTraffic(range = '1h'): Promise<Record<string, unknown>> {
    return this.get<Record<string, unknown>>('/gateway/traffic', { range })
  }

  // Alerts
  async getActiveAlerts(severity?: string): Promise<{ alerts: unknown[] }> {
    const params = severity ? { severity } : undefined
    return this.get<{ alerts: unknown[] }>('/alerts/active', params)
  }

  async acknowledgeAlert(fingerprint: string, note?: string): Promise<unknown> {
    return this.post(`/alerts/${fingerprint}/ack`, { note })
  }

  // Settings
  async getSettings(): Promise<MonitoringSettings> {
    return this.get<MonitoringSettings>('/settings')
  }

  async updateSettings(settings: Partial<MonitoringSettings>): Promise<MonitoringSettings> {
    return this.put<MonitoringSettings>('/settings', settings)
  }

  // Targets
  async getTargets(type?: string): Promise<{ targets: MonitoringTarget[] }> {
    const params = type ? { type } : undefined
    return this.get<{ targets: MonitoringTarget[] }>('/targets', params)
  }

  async createTarget(data: Partial<MonitoringTarget>): Promise<MonitoringTarget> {
    return this.post<MonitoringTarget>('/targets', data)
  }

  async deleteTarget(targetId: string): Promise<void> {
    await this.delete<void>(`/targets/${targetId}`)
  }

  // Events
  async getEvents(
    type?: string,
    level?: string,
    limit = 100,
    offset = 0
  ): Promise<{ events: MonitoringEvent[]; limit: number; offset: number }> {
    return this.get<{ events: MonitoringEvent[]; limit: number; offset: number }>(
      '/events',
      { type, level, limit, offset }
    )
  }

  // Cost
  async getCostSummary(range = '30d'): Promise<CostSummary> {
    return this.get<CostSummary>('/cost/summary', { range })
  }

  async createBudget(data: Partial<Budget>): Promise<Budget> {
    return this.post<Budget>('/cost/budget', data)
  }

  // Adapters
  async getAdapters(): Promise<{ adapters: Adapter[] }> {
    return this.get<{ adapters: Adapter[] }>('/accelerators/adapters')
  }

  async createAdapter(data: Partial<Adapter>): Promise<Adapter> {
    return this.post<Adapter>('/accelerators/adapters', data)
  }
}

// Export singleton instance
export const monitoringClient = new MonitoringClient()

// Legacy exports for backward compatibility
export const getOverview = (range?: string) => monitoringClient.getOverview(range)
export const getDataSourcesHealth = () => monitoringClient.getDataSourcesHealth()
export const getNodes = () => monitoringClient.getNodes()
export const getNodeMetrics = (nodeId: string, range?: string) => monitoringClient.getNodeMetrics(nodeId, range)
export const getAccelerators = () => monitoringClient.getAccelerators()
export const getAcceleratorMetrics = (nodeId: string, device: string, range?: string) =>
  monitoringClient.getAcceleratorMetrics(nodeId, device, range)
export const getGatewayTraffic = (range?: string) => monitoringClient.getGatewayTraffic(range)
export const getActiveAlerts = (severity?: string) => monitoringClient.getActiveAlerts(severity)
export const acknowledgeAlert = (fingerprint: string, note?: string) =>
  monitoringClient.acknowledgeAlert(fingerprint, note)
export const getSettings = () => monitoringClient.getSettings()
export const updateSettings = (settings: Partial<MonitoringSettings>) => monitoringClient.updateSettings(settings)
export const getTargets = (type?: string) => monitoringClient.getTargets(type)
export const createTarget = (data: Partial<MonitoringTarget>) => monitoringClient.createTarget(data)
export const deleteTarget = (targetId: string) => monitoringClient.deleteTarget(targetId)
export const getEvents = (type?: string, level?: string, limit?: number, offset?: number) =>
  monitoringClient.getEvents(type, level, limit, offset)
export const getCostSummary = (range?: string) => monitoringClient.getCostSummary(range)
export const createBudget = (data: Partial<Budget>) => monitoringClient.createBudget(data)
export const getAdapters = () => monitoringClient.getAdapters()
export const createAdapter = (data: Partial<Adapter>) => monitoringClient.createAdapter(data)

export default monitoringClient
