/**
 * API Key Card Component
 */

import type { APIKey } from '../api/gatewayTypes'
import { EnabledStatusBadge, LogPayloadModeBadge } from './StatusBadge'

interface APIKeyCardProps {
  apiKey: APIKey
  onSelect: (id: string) => void
  onDelete?: (id: string) => void
  onRegenerate?: (id: string) => void
}

export function APIKeyCard({ apiKey, onSelect, onDelete, onRegenerate }: APIKeyCardProps) {
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const isExpired = apiKey.expires_at && new Date(apiKey.expires_at) < new Date()

  return (
    <div
      onClick={() => onSelect(apiKey.id)}
      className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 hover:shadow-lg hover:border-teal-300 dark:hover:border-teal-700 transition-all cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 truncate">
            {apiKey.name}
          </h3>
          <code className="text-sm text-stone-500 dark:text-stone-400 font-mono">
            {apiKey.key_prefix}...
          </code>
        </div>
        <EnabledStatusBadge enabled={apiKey.enabled && !isExpired} size="sm" />
      </div>

      {/* Description */}
      {apiKey.description && (
        <p className="text-sm text-stone-600 dark:text-stone-400 mb-3 line-clamp-2">
          {apiKey.description}
        </p>
      )}

      {/* Expired Warning */}
      {isExpired && (
        <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-2 mb-3">
          <p className="text-xs text-red-600 dark:text-red-400">
            此密钥已于 {formatDate(apiKey.expires_at)} 过期
          </p>
        </div>
      )}

      {/* Access Control */}
      <div className="space-y-2 mb-3">
        {apiKey.allowed_models.length > 0 && (
          <div className="flex items-start gap-2 text-sm">
            <span className="text-stone-500 dark:text-stone-400 shrink-0">模型:</span>
            <div className="flex flex-wrap gap-1">
              {apiKey.allowed_models.slice(0, 3).map((model) => (
                <span
                  key={model}
                  className="px-1.5 py-0.5 text-xs bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-300 rounded"
                >
                  {model}
                </span>
              ))}
              {apiKey.allowed_models.length > 3 && (
                <span className="text-xs text-stone-400">+{apiKey.allowed_models.length - 3}</span>
              )}
            </div>
          </div>
        )}
        {apiKey.allowed_models.length === 0 && (
          <div className="text-sm text-stone-500 dark:text-stone-400">
            <span className="text-green-600 dark:text-green-400">所有模型</span>
          </div>
        )}
      </div>

      {/* Rate Limits */}
      <div className="flex items-center gap-4 text-sm text-stone-600 dark:text-stone-400 mb-3">
        {apiKey.rate_limit.requests_per_minute && (
          <span className="flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            {apiKey.rate_limit.requests_per_minute}/min
          </span>
        )}
        {apiKey.rate_limit.tokens_per_minute && (
          <span className="flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
            </svg>
            {apiKey.rate_limit.tokens_per_minute} tok/min
          </span>
        )}
        <LogPayloadModeBadge mode={apiKey.log_payload_mode} />
      </div>

      {/* Usage Quota */}
      {apiKey.quota.max_tokens && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs text-stone-500 dark:text-stone-400 mb-1">
            <span>Token 配额</span>
            <span>{apiKey.quota.current_tokens_used?.toLocaleString() || 0} / {apiKey.quota.max_tokens.toLocaleString()}</span>
          </div>
          <div className="h-1.5 bg-stone-200 dark:bg-stone-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-teal-500 rounded-full"
              style={{
                width: `${Math.min(100, ((apiKey.quota.current_tokens_used || 0) / apiKey.quota.max_tokens) * 100)}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Actions */}
      {(onRegenerate || onDelete) && (
        <div className="flex gap-2 pt-3 border-t border-stone-200 dark:border-stone-700">
          {onRegenerate && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onRegenerate(apiKey.id)
              }}
              className="flex-1 px-3 py-1.5 border border-stone-300 dark:border-stone-600 text-stone-700 dark:text-stone-300 text-sm rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors"
            >
              重新生成
            </button>
          )}
          {onDelete && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete(apiKey.id)
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
          <span>创建于 {formatDate(apiKey.created_at)}</span>
          <span>
            {apiKey.last_used_at ? `上次使用 ${formatDate(apiKey.last_used_at)}` : '从未使用'}
          </span>
        </div>
      </div>
    </div>
  )
}
