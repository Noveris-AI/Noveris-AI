/**
 * Node Card Component
 */

import { Link } from 'react-router-dom'
import type { Node } from '../api/nodeManagementTypes'
import { NodeStatusBadge } from './StatusBadge'
import { AcceleratorSummary } from './AcceleratorIcon'

interface NodeCardProps {
  node: Node
  onSelect?: (nodeId: string) => void
}

export function NodeCard({ node, onSelect }: NodeCardProps) {
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatMemory = (mb?: number) => {
    if (!mb) return '-'
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)} GB`
    }
    return `${mb} MB`
  }

  return (
    <div
      className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => onSelect?.(node.id)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Link
              to={`/dashboard/nodes/${node.id}`}
              className="text-lg font-semibold text-stone-900 dark:text-stone-100 hover:text-teal-600 dark:hover:text-teal-400 truncate"
              onClick={(e) => e.stopPropagation()}
            >
              {node.display_name || node.name}
            </Link>
            <NodeStatusBadge status={node.status} size="sm" />
          </div>
          <p className="text-sm text-stone-500 dark:text-stone-400 truncate mt-0.5">
            {node.host}:{node.port}
          </p>
        </div>
      </div>

      {/* System Info */}
      <div className="space-y-2 text-sm">
        {/* OS & Kernel */}
        {(node.os_release || node.kernel_version) && (
          <div className="flex items-center gap-2 text-stone-600 dark:text-stone-400">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
            </svg>
            <span className="truncate">
              {node.os_release || '未知系统'}
              {node.architecture && ` (${node.architecture})`}
            </span>
          </div>
        )}

        {/* Hardware */}
        <div className="flex items-center gap-4 text-stone-600 dark:text-stone-400">
          {node.cpu_cores && (
            <span className="flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              {node.cpu_cores} 核
            </span>
          )}
          {node.mem_mb && (
            <span className="flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              {formatMemory(node.mem_mb)}
            </span>
          )}
        </div>

        {/* Accelerators */}
        <div className="pt-1">
          <AcceleratorSummary summary={node.accelerator_summary} size="sm" />
        </div>

        {/* Groups */}
        {node.group_names.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {node.group_names.slice(0, 3).map((groupName) => (
              <span
                key={groupName}
                className="px-2 py-0.5 text-xs bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-300 rounded"
              >
                {groupName}
              </span>
            ))}
            {node.group_names.length > 3 && (
              <span className="px-2 py-0.5 text-xs text-stone-400">
                +{node.group_names.length - 3}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-3 pt-3 border-t border-stone-100 dark:border-stone-700 flex items-center justify-between text-xs text-stone-400">
        <span>最后在线: {formatDate(node.last_seen_at)}</span>
        <span>{node.connection_type === 'local' ? '本地' : 'SSH'}</span>
      </div>
    </div>
  )
}
