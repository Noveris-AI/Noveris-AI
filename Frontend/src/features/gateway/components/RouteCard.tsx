/**
 * Route Card Component
 */

import type { Route } from '../api/gatewayTypes'
import { EnabledStatusBadge } from './StatusBadge'

interface RouteCardProps {
  route: Route
  onSelect: (id: string) => void
  onDelete?: (id: string) => void
}

export function RouteCard({ route, onSelect, onDelete }: RouteCardProps) {
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatMatch = (match: Route['match']) => {
    const parts = []
    if (match.endpoint) parts.push({ label: '端点', value: match.endpoint })
    if (match.virtual_model) parts.push({ label: '模型', value: match.virtual_model })
    if (match.tenant_id) parts.push({ label: '租户', value: match.tenant_id })
    if (match.api_key_id) parts.push({ label: '密钥', value: match.api_key_id })
    if (match.tags && Object.keys(match.tags).length > 0) {
      parts.push({
        label: '标签',
        value: Object.entries(match.tags).map(([k, v]) => `${k}=${v}`).join(', '),
      })
    }
    return parts
  }

  const matchParts = formatMatch(route.match)

  return (
    <div
      onClick={() => onSelect(route.id)}
      className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 hover:shadow-lg hover:border-teal-300 dark:hover:border-teal-700 transition-all cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="flex items-center justify-center w-8 h-8 rounded-full bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 text-sm font-bold">
            {route.priority}
          </span>
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 truncate">
              {route.name}
            </h3>
          </div>
        </div>
        <EnabledStatusBadge enabled={route.enabled} size="sm" />
      </div>

      {/* Description */}
      {route.description && (
        <p className="text-sm text-stone-600 dark:text-stone-400 mb-3 line-clamp-2">
          {route.description}
        </p>
      )}

      {/* Match Criteria */}
      <div className="bg-stone-50 dark:bg-stone-900 rounded-lg p-3 mb-3">
        <div className="text-xs text-stone-500 dark:text-stone-400 mb-2">匹配条件</div>
        {matchParts.length > 0 ? (
          <div className="space-y-1">
            {matchParts.map((part, index) => (
              <div key={index} className="flex items-center gap-2 text-sm">
                <span className="text-stone-500 dark:text-stone-400 shrink-0 w-10">{part.label}:</span>
                <code className="text-stone-700 dark:text-stone-300 truncate">{part.value}</code>
              </div>
            ))}
          </div>
        ) : (
          <span className="text-sm text-green-600 dark:text-green-400">所有请求</span>
        )}
      </div>

      {/* Upstreams */}
      <div className="flex items-center gap-4 text-sm text-stone-600 dark:text-stone-400 mb-3">
        <span className="flex items-center gap-1">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
          </svg>
          {route.action.primary_upstreams.length} 个主上游
        </span>
        {route.action.fallback_upstreams && route.action.fallback_upstreams.length > 0 && (
          <span className="flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {route.action.fallback_upstreams.length} 个备用
          </span>
        )}
      </div>

      {/* Features */}
      <div className="flex flex-wrap gap-2 mb-3">
        {route.action.cache_policy?.enabled && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
            </svg>
            缓存 {route.action.cache_policy.ttl_seconds}s
          </span>
        )}
        {route.action.retry_policy && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 rounded">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            重试 {route.action.retry_policy.max_retries}次
          </span>
        )}
        {route.action.timeout_ms_override && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            超时 {route.action.timeout_ms_override}ms
          </span>
        )}
      </div>

      {/* Actions */}
      {onDelete && (
        <div className="flex gap-2 pt-3 border-t border-stone-200 dark:border-stone-700">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete(route.id)
            }}
            className="px-3 py-1.5 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 text-sm rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
          >
            删除
          </button>
        </div>
      )}

      {/* Timestamp */}
      <div className="mt-3 pt-2 border-t border-stone-100 dark:border-stone-700">
        <div className="flex items-center justify-between text-xs text-stone-400">
          <span>创建于 {formatDate(route.created_at)}</span>
          <span>更新于 {formatDate(route.updated_at)}</span>
        </div>
      </div>
    </div>
  )
}
