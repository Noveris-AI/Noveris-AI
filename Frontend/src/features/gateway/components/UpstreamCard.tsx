/**
 * Upstream Card Component
 */

import type { Upstream } from '../api/gatewayTypes'
import { UpstreamTypeBadge, HealthStatusBadge, EnabledStatusBadge, CapabilityBadge } from './StatusBadge'

interface UpstreamCardProps {
  upstream: Upstream
  onSelect: (id: string) => void
  onTest?: (id: string) => void
  onDelete?: (id: string) => void
  isTestPending?: boolean
}

export function UpstreamCard({ upstream, onSelect, onTest, onDelete, isTestPending }: UpstreamCardProps) {
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div
      onClick={() => onSelect(upstream.id)}
      className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 hover:shadow-lg hover:border-teal-300 dark:hover:border-teal-700 transition-all cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 truncate">
            {upstream.name}
          </h3>
          <p className="text-sm text-stone-500 dark:text-stone-400 truncate mt-0.5">
            {upstream.base_url}
          </p>
        </div>
        <UpstreamTypeBadge type={upstream.type} />
      </div>

      {/* Status Row */}
      <div className="flex items-center gap-3 mb-3">
        <EnabledStatusBadge enabled={upstream.enabled} size="sm" />
        <HealthStatusBadge status={upstream.health_status} size="sm" />
      </div>

      {/* Description */}
      {upstream.description && (
        <p className="text-sm text-stone-600 dark:text-stone-400 mb-3 line-clamp-2">
          {upstream.description}
        </p>
      )}

      {/* Capabilities */}
      {upstream.supported_capabilities.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {upstream.supported_capabilities.slice(0, 4).map((cap) => (
            <CapabilityBadge key={cap} capability={cap} />
          ))}
          {upstream.supported_capabilities.length > 4 && (
            <span className="inline-flex items-center px-1.5 py-0.5 text-xs text-stone-400">
              +{upstream.supported_capabilities.length - 4}
            </span>
          )}
        </div>
      )}

      {/* Config Info */}
      <div className="flex items-center gap-4 text-sm text-stone-600 dark:text-stone-400 mb-3">
        <span className="flex items-center gap-1">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {upstream.timeout_ms}ms
        </span>
        <span className="flex items-center gap-1">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {upstream.max_retries} 重试
        </span>
        {upstream.has_credentials && (
          <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
            已配置凭证
          </span>
        )}
      </div>

      {/* Health Check Error */}
      {upstream.health_check_error && (
        <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-2 mb-3">
          <p className="text-xs text-red-600 dark:text-red-400 line-clamp-2">
            {upstream.health_check_error}
          </p>
        </div>
      )}

      {/* Actions */}
      {(onTest || onDelete) && (
        <div className="flex gap-2 pt-3 border-t border-stone-200 dark:border-stone-700">
          {onTest && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onTest(upstream.id)
              }}
              disabled={isTestPending}
              className="flex-1 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white text-sm rounded-lg transition-colors disabled:cursor-not-allowed"
            >
              {isTestPending ? '测试中...' : '测试连接'}
            </button>
          )}
          {onDelete && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete(upstream.id)
              }}
              className="px-3 py-1.5 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 text-sm rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              删除
            </button>
          )}
        </div>
      )}

      {/* Timestamp */}
      <div className="mt-3 pt-2 border-t border-stone-100 dark:border-stone-700">
        <div className="flex items-center justify-between text-xs text-stone-400">
          <span>创建于 {formatDate(upstream.created_at)}</span>
          {upstream.last_health_check_at && (
            <span>上次检查 {formatDate(upstream.last_health_check_at)}</span>
          )}
        </div>
      </div>
    </div>
  )
}
