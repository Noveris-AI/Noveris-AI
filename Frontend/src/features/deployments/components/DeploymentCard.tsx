/**
 * Deployment Card Component
 */

import type { Deployment } from '../api/deploymentTypes'
import { DeploymentStatusBadge, HealthStatusBadge, FrameworkBadge } from './StatusBadge'

interface DeploymentCardProps {
  deployment: Deployment
  onSelect: (id: string) => void
  onStart?: (id: string) => void
  onStop?: (id: string) => void
}

export function DeploymentCard({ deployment, onSelect, onStart, onStop }: DeploymentCardProps) {
  const isRunning = deployment.status === 'RUNNING'
  const isStopped = deployment.status === 'STOPPED' || deployment.status === 'FAILED'
  const isActionable = isRunning || isStopped

  return (
    <div
      onClick={() => onSelect(deployment.id)}
      className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 hover:shadow-lg hover:border-teal-300 dark:hover:border-teal-700 transition-all cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 truncate">
            {deployment.display_name || deployment.name}
          </h3>
          <p className="text-sm text-stone-500 dark:text-stone-400 truncate mt-0.5">
            {deployment.model_repo_id}
          </p>
        </div>
        <FrameworkBadge framework={deployment.framework} />
      </div>

      {/* Status Row */}
      <div className="flex items-center gap-3 mb-3">
        <DeploymentStatusBadge status={deployment.status} size="sm" />
        {deployment.status === 'RUNNING' && (
          <HealthStatusBadge status={deployment.health_status} size="sm" />
        )}
      </div>

      {/* Node Info */}
      <div className="flex items-center gap-2 text-sm text-stone-600 dark:text-stone-400 mb-3">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
        </svg>
        <span className="truncate">
          {deployment.node_name || deployment.node_host || '未知节点'}
        </span>
      </div>

      {/* GPU Info */}
      {deployment.gpu_devices && deployment.gpu_devices.length > 0 && (
        <div className="flex items-center gap-2 text-sm text-stone-600 dark:text-stone-400 mb-3">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
          </svg>
          <span>
            GPU {deployment.gpu_devices.join(', ')} (TP={deployment.tensor_parallel_size})
          </span>
        </div>
      )}

      {/* Endpoint Info */}
      {deployment.status === 'RUNNING' && deployment.endpoints?.openai_base && (
        <div className="bg-stone-50 dark:bg-stone-900 rounded-lg p-2 mb-3">
          <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">API Endpoint</div>
          <code className="text-xs text-stone-700 dark:text-stone-300 break-all">
            {deployment.endpoints.openai_base}
          </code>
        </div>
      )}

      {/* Error Message */}
      {deployment.error_message && (
        <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-2 mb-3">
          <p className="text-xs text-red-600 dark:text-red-400 line-clamp-2">
            {deployment.error_message}
          </p>
        </div>
      )}

      {/* Actions */}
      {isActionable && (
        <div className="flex gap-2 pt-2 border-t border-stone-200 dark:border-stone-700">
          {isStopped && onStart && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onStart(deployment.id)
              }}
              className="flex-1 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition-colors"
            >
              启动
            </button>
          )}
          {isRunning && onStop && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onStop(deployment.id)
              }}
              className="flex-1 px-3 py-1.5 bg-orange-600 hover:bg-orange-700 text-white text-sm rounded-lg transition-colors"
            >
              停止
            </button>
          )}
        </div>
      )}

      {/* Timestamp */}
      <div className="mt-3 pt-2 border-t border-stone-100 dark:border-stone-700">
        <div className="flex items-center justify-between text-xs text-stone-400">
          <span>创建于 {new Date(deployment.created_at).toLocaleDateString()}</span>
          {deployment.started_at && (
            <span>启动于 {new Date(deployment.started_at).toLocaleString()}</span>
          )}
        </div>
      </div>
    </div>
  )
}
