/**
 * Deployment Status Badge Component
 */

import type { DeploymentStatus, HealthStatus, DeploymentFramework } from '../api/deploymentTypes'

interface DeploymentStatusBadgeProps {
  status: DeploymentStatus
  size?: 'sm' | 'md'
}

const statusConfig: Record<DeploymentStatus, { label: string; bg: string; text: string; dot: string }> = {
  PENDING: {
    label: '等待中',
    bg: 'bg-stone-100 dark:bg-stone-800',
    text: 'text-stone-600 dark:text-stone-400',
    dot: 'bg-stone-400',
  },
  DOWNLOADING: {
    label: '下载中',
    bg: 'bg-blue-100 dark:bg-blue-900/30',
    text: 'text-blue-600 dark:text-blue-400',
    dot: 'bg-blue-500 animate-pulse',
  },
  INSTALLING: {
    label: '安装中',
    bg: 'bg-purple-100 dark:bg-purple-900/30',
    text: 'text-purple-600 dark:text-purple-400',
    dot: 'bg-purple-500 animate-pulse',
  },
  STARTING: {
    label: '启动中',
    bg: 'bg-amber-100 dark:bg-amber-900/30',
    text: 'text-amber-600 dark:text-amber-400',
    dot: 'bg-amber-500 animate-pulse',
  },
  RUNNING: {
    label: '运行中',
    bg: 'bg-green-100 dark:bg-green-900/30',
    text: 'text-green-600 dark:text-green-400',
    dot: 'bg-green-500',
  },
  STOPPED: {
    label: '已停止',
    bg: 'bg-stone-100 dark:bg-stone-800',
    text: 'text-stone-600 dark:text-stone-400',
    dot: 'bg-stone-400',
  },
  FAILED: {
    label: '失败',
    bg: 'bg-red-100 dark:bg-red-900/30',
    text: 'text-red-600 dark:text-red-400',
    dot: 'bg-red-500',
  },
  DELETING: {
    label: '删除中',
    bg: 'bg-orange-100 dark:bg-orange-900/30',
    text: 'text-orange-600 dark:text-orange-400',
    dot: 'bg-orange-500 animate-pulse',
  },
}

export function DeploymentStatusBadge({ status, size = 'md' }: DeploymentStatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.PENDING

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full ${config.bg} ${config.text} ${
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  )
}

// Health Status Badge
interface HealthStatusBadgeProps {
  status: HealthStatus
  size?: 'sm' | 'md'
}

const healthConfig: Record<HealthStatus, { label: string; color: string }> = {
  unknown: { label: '未知', color: 'text-stone-500' },
  healthy: { label: '健康', color: 'text-green-500' },
  unhealthy: { label: '异常', color: 'text-red-500' },
  starting: { label: '启动中', color: 'text-amber-500' },
}

export function HealthStatusBadge({ status, size = 'md' }: HealthStatusBadgeProps) {
  const config = healthConfig[status] || healthConfig.unknown

  return (
    <span className={`inline-flex items-center gap-1 ${config.color} ${size === 'sm' ? 'text-xs' : 'text-sm'}`}>
      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        {status === 'healthy' ? (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        ) : status === 'unhealthy' ? (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        ) : status === 'starting' ? (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        ) : (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        )}
      </svg>
      {config.label}
    </span>
  )
}

// Framework Badge
interface FrameworkBadgeProps {
  framework: DeploymentFramework
}

const frameworkConfig: Record<DeploymentFramework, { label: string; bg: string; text: string }> = {
  vllm: {
    label: 'vLLM',
    bg: 'bg-teal-100 dark:bg-teal-900/30',
    text: 'text-teal-700 dark:text-teal-300',
  },
  sglang: {
    label: 'SGLang',
    bg: 'bg-indigo-100 dark:bg-indigo-900/30',
    text: 'text-indigo-700 dark:text-indigo-300',
  },
  xinference: {
    label: 'Xinference',
    bg: 'bg-violet-100 dark:bg-violet-900/30',
    text: 'text-violet-700 dark:text-violet-300',
  },
}

export function FrameworkBadge({ framework }: FrameworkBadgeProps) {
  const config = frameworkConfig[framework] || frameworkConfig.vllm

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  )
}
