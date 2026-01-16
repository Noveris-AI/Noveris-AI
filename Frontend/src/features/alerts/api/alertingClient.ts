/**
 * Alerting API Client
 *
 * API client for alerting operations (rules, instances, channels, silences).
 */

import { BaseApiClient } from '@shared/lib/apiClient'
import type {
  AlertRule,
  AlertRuleCreateRequest,
  AlertRuleUpdateRequest,
  AlertRuleListResponse,
  AlertRuleSearchParams,
  AlertInstance,
  AlertInstanceListResponse,
  AlertInstanceSearchParams,
  AlertAcknowledgeRequest,
  AlertBulkAcknowledgeRequest,
  NotificationChannel,
  NotificationChannelCreateRequest,
  NotificationChannelUpdateRequest,
  NotificationChannelListResponse,
  NotificationChannelSearchParams,
  NotificationChannelTestRequest,
  NotificationChannelTestResponse,
  AlertSilence,
  AlertSilenceCreateRequest,
  AlertSilenceUpdateRequest,
  AlertStatistics,
} from './alertingTypes'

class AlertingClient extends BaseApiClient {
  constructor() {
    super('/alerts')
  }

  // ==========================================================================
  // Alert Rules
  // ==========================================================================

  async listAlertRules(params: AlertRuleSearchParams = {}): Promise<AlertRuleListResponse> {
    return this.get<AlertRuleListResponse>('/rules', params)
  }

  async getAlertRule(ruleId: string): Promise<AlertRule> {
    return this.get<AlertRule>(`/rules/${ruleId}`)
  }

  async createAlertRule(data: AlertRuleCreateRequest): Promise<AlertRule> {
    return this.post<AlertRule>('/rules', data)
  }

  async updateAlertRule(ruleId: string, data: AlertRuleUpdateRequest): Promise<AlertRule> {
    return this.put<AlertRule>(`/rules/${ruleId}`, data)
  }

  async deleteAlertRule(ruleId: string): Promise<void> {
    await this.delete<void>(`/rules/${ruleId}`)
  }

  async enableAlertRule(ruleId: string): Promise<AlertRule> {
    return this.post<AlertRule>(`/rules/${ruleId}:enable`, {})
  }

  async disableAlertRule(ruleId: string): Promise<AlertRule> {
    return this.post<AlertRule>(`/rules/${ruleId}:disable`, {})
  }

  // ==========================================================================
  // Alert Instances
  // ==========================================================================

  async listAlerts(params: AlertInstanceSearchParams = {}): Promise<AlertInstanceListResponse> {
    return this.get<AlertInstanceListResponse>('', params)
  }

  async getAlert(alertId: string): Promise<AlertInstance> {
    return this.get<AlertInstance>(`/${alertId}`)
  }

  async acknowledgeAlert(alertId: string, data: AlertAcknowledgeRequest = {}): Promise<AlertInstance> {
    return this.post<AlertInstance>(`/${alertId}:acknowledge`, data)
  }

  async resolveAlert(alertId: string): Promise<AlertInstance> {
    return this.post<AlertInstance>(`/${alertId}:resolve`, {})
  }

  async bulkAcknowledgeAlerts(data: AlertBulkAcknowledgeRequest): Promise<{
    total_count: number
    success_count: number
    failed_count: number
    results: Array<{ alert_id: string; status: string; error?: string }>
  }> {
    return this.post(':acknowledge-bulk', data)
  }

  // ==========================================================================
  // Statistics
  // ==========================================================================

  async getStatistics(): Promise<AlertStatistics> {
    return this.get<AlertStatistics>('/statistics')
  }

  // ==========================================================================
  // Notification Channels
  // ==========================================================================

  async listChannels(params: NotificationChannelSearchParams = {}): Promise<NotificationChannelListResponse> {
    return this.get<NotificationChannelListResponse>('/channels', params)
  }

  async getChannel(channelId: string): Promise<NotificationChannel> {
    return this.get<NotificationChannel>(`/channels/${channelId}`)
  }

  async createChannel(data: NotificationChannelCreateRequest): Promise<NotificationChannel> {
    return this.post<NotificationChannel>('/channels', data)
  }

  async updateChannel(channelId: string, data: NotificationChannelUpdateRequest): Promise<NotificationChannel> {
    return this.put<NotificationChannel>(`/channels/${channelId}`, data)
  }

  async deleteChannel(channelId: string): Promise<void> {
    await this.delete<void>(`/channels/${channelId}`)
  }

  async testChannel(channelId: string, data: NotificationChannelTestRequest = {}): Promise<NotificationChannelTestResponse> {
    return this.post<NotificationChannelTestResponse>(`/channels/${channelId}:test`, data)
  }

  // ==========================================================================
  // Alert Silences
  // ==========================================================================

  async listSilences(activeOnly: boolean = false): Promise<{ items: AlertSilence[]; total: number }> {
    return this.get('/silences', { active_only: activeOnly })
  }

  async getSilence(silenceId: string): Promise<AlertSilence> {
    return this.get<AlertSilence>(`/silences/${silenceId}`)
  }

  async createSilence(data: AlertSilenceCreateRequest): Promise<AlertSilence> {
    return this.post<AlertSilence>('/silences', data)
  }

  async updateSilence(silenceId: string, data: AlertSilenceUpdateRequest): Promise<AlertSilence> {
    return this.put<AlertSilence>(`/silences/${silenceId}`, data)
  }

  async deleteSilence(silenceId: string): Promise<void> {
    await this.delete<void>(`/silences/${silenceId}`)
  }
}

export const alertingClient = new AlertingClient()
export default alertingClient
