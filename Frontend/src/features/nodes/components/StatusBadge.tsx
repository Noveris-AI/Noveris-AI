/**
 * Node Status Badge Component
 */

import type { NodeStatus, JobStatus } from '../api/nodeManagementTypes'

interface StatusBadgeProps {
  status: NodeStatus | JobStatus
  size?: 'sm' | 'md'
}

const nodeStatusConfig: Record<NodeStatus, { label: string; color: string; dotColor: string }> = {
  NEW: {
    label: '新建',
    color: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    dotColor: 'bg-blue-500',
  },
  READY: {
    label: '就绪',
    color: 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    dotColor: 'bg-green-500',
  },
  UNREACHABLE: {
    label: '不可达',
    color: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    dotColor: 'bg-red-500',
  },
  MAINTENANCE: {
    label: '维护中',
    color: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
    dotColor: 'bg-amber-500',
  },
  DECOMMISSIONED: {
    label: '已下线',
    color: 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400',
    dotColor: 'bg-stone-400',
  },
}

const jobStatusConfig: Record<JobStatus, { label: string; color: string; dotColor: string }> = {
  PENDING: {
    label: '等待中',
    color: 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400',
    dotColor: 'bg-stone-400',
  },
  RUNNING: {
    label: '运行中',
    color: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    dotColor: 'bg-blue-500 animate-pulse',
  },
  SUCCEEDED: {
    label: '成功',
    color: 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    dotColor: 'bg-green-500',
  },
  FAILED: {
    label: '失败',
    color: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    dotColor: 'bg-red-500',
  },
  CANCELED: {
    label: '已取消',
    color: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
    dotColor: 'bg-amber-500',
  },
}

export function NodeStatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const config = nodeStatusConfig[status as NodeStatus]
  if (!config) return null

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${config.color} ${sizeClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dotColor}`} />
      {config.label}
    </span>
  )
}

export function JobStatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const config = jobStatusConfig[status as JobStatus]
  if (!config) return null

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${config.color} ${sizeClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dotColor}`} />
      {config.label}
    </span>
  )
}
