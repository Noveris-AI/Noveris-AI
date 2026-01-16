/**
 * Virtual Model Card Component
 */

import type { VirtualModel } from '../api/gatewayTypes'
import { EnabledStatusBadge, CapabilityBadge } from './StatusBadge'

interface VirtualModelCardProps {
  model: VirtualModel
  onSelect: (id: string) => void
  onDelete?: (id: string) => void
}

export function VirtualModelCard({ model, onSelect, onDelete }: VirtualModelCardProps) {
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
      onClick={() => onSelect(model.id)}
      className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 hover:shadow-lg hover:border-teal-300 dark:hover:border-teal-700 transition-all cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 truncate">
            {model.display_name || model.name}
          </h3>
          <code className="text-sm text-stone-500 dark:text-stone-400 font-mono">
            {model.name}
          </code>
        </div>
        <EnabledStatusBadge enabled={model.enabled} size="sm" />
      </div>

      {/* Description */}
      {model.description && (
        <p className="text-sm text-stone-600 dark:text-stone-400 mb-3 line-clamp-2">
          {model.description}
        </p>
      )}

      {/* Capabilities */}
      {model.capabilities.length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">支持的能力</div>
          <div className="flex flex-wrap gap-1">
            {model.capabilities.slice(0, 5).map((cap) => (
              <CapabilityBadge key={cap} capability={cap} />
            ))}
            {model.capabilities.length > 5 && (
              <span className="inline-flex items-center px-1.5 py-0.5 text-xs text-stone-400">
                +{model.capabilities.length - 5}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Tags */}
      {Object.keys(model.tags).length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">标签</div>
          <div className="flex flex-wrap gap-1">
            {Object.entries(model.tags).slice(0, 4).map(([key, value]) => (
              <span
                key={key}
                className="px-2 py-0.5 text-xs bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded"
              >
                {key}={value}
              </span>
            ))}
            {Object.keys(model.tags).length > 4 && (
              <span className="text-xs text-stone-400">+{Object.keys(model.tags).length - 4}</span>
            )}
          </div>
        </div>
      )}

      {/* Default Route */}
      {model.default_route_id && (
        <div className="flex items-center gap-2 text-sm text-stone-600 dark:text-stone-400 mb-3">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
          <span>已关联默认路由</span>
        </div>
      )}

      {/* Actions */}
      {onDelete && (
        <div className="flex gap-2 pt-3 border-t border-stone-200 dark:border-stone-700">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete(model.id)
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
          <span>创建于 {formatDate(model.created_at)}</span>
          <span>更新于 {formatDate(model.updated_at)}</span>
        </div>
      </div>
    </div>
  )
}
