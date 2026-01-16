/**
 * Alerting API Types
 *
 * TypeScript interfaces for alerting system entities.
 */

// Enums
export type AlertSeverity = 'CRITICAL' | 'WARNING' | 'INFO'
export type AlertState = 'FIRING' | 'RESOLVED' | 'ACKNOWLEDGED' | 'SILENCED'
export type AlertRuleType = 'node_status' | 'metric_threshold' | 'job_failure' | 'connectivity' | 'custom'
export type NotificationChannelType = 'WEBHOOK' | 'EMAIL' | 'SLACK' | 'PAGERDUTY' | 'TEAMS'
export type ComparisonOperator = 'gt' | 'gte' | 'lt' | 'lte' | 'eq' | 'neq'

// Alert Rule
export interface AlertRule {
  id: string
  tenant_id: string
  name: string
  description?: string
  enabled: boolean
  rule_type: AlertRuleType
  condition: Record<string, unknown>
  severity: AlertSeverity
  target_all_nodes: boolean
  target_node_ids?: string[]
  target_group_ids?: string[]
  target_tags?: string[]
  evaluation_interval: number
  for_duration: number
  notification_channel_ids?: string[]
  notification_template?: string
  labels: Record<string, string>
  annotations: Record<string, string>
  created_at: string
  updated_at?: string
  created_by?: string
  active_alerts_count: number
}

export interface AlertRuleCreateRequest {
  name: string
  description?: string
  enabled?: boolean
  rule_type: AlertRuleType
  condition: Record<string, unknown>
  severity?: AlertSeverity
  target_all_nodes?: boolean
  target_node_ids?: string[]
  target_group_ids?: string[]
  target_tags?: string[]
  evaluation_interval?: number
  for_duration?: number
  notification_channel_ids?: string[]
  notification_template?: string
  labels?: Record<string, string>
  annotations?: Record<string, string>
}

export interface AlertRuleUpdateRequest {
  name?: string
  description?: string
  enabled?: boolean
  severity?: AlertSeverity
  condition?: Record<string, unknown>
  target_all_nodes?: boolean
  target_node_ids?: string[]
  target_group_ids?: string[]
  target_tags?: string[]
  evaluation_interval?: number
  for_duration?: number
  notification_channel_ids?: string[]
  notification_template?: string
  labels?: Record<string, string>
  annotations?: Record<string, string>
}

// Alert Instance
export interface AlertInstance {
  id: string
  tenant_id: string
  rule_id: string
  fingerprint: string
  title: string
  message?: string
  severity: AlertSeverity
  state: AlertState
  node_id?: string
  node_name?: string
  group_id?: string
  labels: Record<string, string>
  annotations: Record<string, string>
  metric_name?: string
  metric_value?: number
  threshold_value?: number
  fired_at: string
  resolved_at?: string
  acknowledged_at?: string
  acknowledged_by?: string
  notifications_sent: number
  last_notification_at?: string
  duration_seconds?: number
}

export interface AlertAcknowledgeRequest {
  comment?: string
}

export interface AlertBulkAcknowledgeRequest {
  alert_ids: string[]
  comment?: string
}

// Notification Channel
export interface NotificationChannel {
  id: string
  tenant_id: string
  name: string
  description?: string
  channel_type: NotificationChannelType
  enabled: boolean
  config: Record<string, unknown>
  send_resolved: boolean
  rate_limit: number
  labels: Record<string, string>
  created_at: string
  updated_at?: string
  created_by?: string
  last_success_at?: string
  last_failure_at?: string
  failure_count: number
}

export interface NotificationChannelCreateRequest {
  name: string
  description?: string
  channel_type: NotificationChannelType
  enabled?: boolean
  config: Record<string, unknown>
  send_resolved?: boolean
  rate_limit?: number
  labels?: Record<string, string>
}

export interface NotificationChannelUpdateRequest {
  name?: string
  description?: string
  enabled?: boolean
  config?: Record<string, unknown>
  send_resolved?: boolean
  rate_limit?: number
  labels?: Record<string, string>
}

export interface NotificationChannelTestRequest {
  test_message?: string
}

export interface NotificationChannelTestResponse {
  success: boolean
  message: string
  response_time_ms?: number
  error_details?: string
}

// Alert Silence
export interface LabelMatcher {
  name: string
  value: string
  is_regex: boolean
  is_negative: boolean
}

export interface AlertSilence {
  id: string
  tenant_id: string
  name: string
  comment?: string
  matchers: LabelMatcher[]
  starts_at: string
  ends_at: string
  created_at: string
  created_by?: string
  is_active: boolean
}

export interface AlertSilenceCreateRequest {
  name: string
  comment?: string
  matchers: LabelMatcher[]
  starts_at: string
  ends_at: string
}

export interface AlertSilenceUpdateRequest {
  name?: string
  comment?: string
  matchers?: LabelMatcher[]
  ends_at?: string
}

// Statistics
export interface AlertStatistics {
  total_rules: number
  enabled_rules: number
  total_alerts: number
  firing_alerts: number
  resolved_alerts: number
  acknowledged_alerts: number
  by_severity: Record<string, number>
  by_rule_type: Record<string, number>
  by_node: Array<{ node_id: string; node_name: string; count: number }>
  generated_at: string
}

// Response types
export interface AlertRuleListResponse {
  items: AlertRule[]
  total: number
  limit: number
  offset: number
}

export interface AlertInstanceListResponse {
  items: AlertInstance[]
  total: number
  limit: number
  offset: number
}

export interface NotificationChannelListResponse {
  items: NotificationChannel[]
  total: number
  limit: number
  offset: number
}

// Search params
export interface AlertRuleSearchParams {
  enabled_only?: boolean
  rule_type?: AlertRuleType
  limit?: number
  offset?: number
}

export interface AlertInstanceSearchParams {
  state?: AlertState
  severity?: AlertSeverity
  rule_id?: string
  node_id?: string
  hours?: number
  limit?: number
  offset?: number
}

export interface NotificationChannelSearchParams {
  enabled_only?: boolean
  channel_type?: NotificationChannelType
  limit?: number
  offset?: number
}

// Condition types for rule creation
export interface NodeStatusCondition {
  statuses: string[]
}

export interface MetricThresholdCondition {
  metric_name: string
  operator: ComparisonOperator
  threshold: number
  unit?: string
}

export interface JobFailureCondition {
  job_types?: string[]
  consecutive_failures: number
  include_cancelled?: boolean
}

export interface ConnectivityCondition {
  timeout_seconds: number
  retry_count: number
}
