/**
 * Accelerator Icons Component
 */

import type { AcceleratorType } from '../api/nodeManagementTypes'

interface AcceleratorIconProps {
  type: AcceleratorType
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  count?: number
}

const acceleratorConfig: Record<AcceleratorType, { label: string; color: string; shortLabel: string }> = {
  nvidia_gpu: {
    label: 'NVIDIA GPU',
    shortLabel: 'NVIDIA',
    color: 'text-green-600 dark:text-green-400',
  },
  amd_gpu: {
    label: 'AMD GPU',
    shortLabel: 'AMD',
    color: 'text-red-600 dark:text-red-400',
  },
  intel_gpu: {
    label: 'Intel GPU',
    shortLabel: 'Intel',
    color: 'text-blue-600 dark:text-blue-400',
  },
  huawei_npu: {
    label: 'Huawei Ascend NPU',
    shortLabel: 'Ascend',
    color: 'text-rose-600 dark:text-rose-400',
  },
  thead_npu: {
    label: 'T-Head NPU',
    shortLabel: 'T-Head',
    color: 'text-violet-600 dark:text-violet-400',
  },
  other: {
    label: 'Other Accelerator',
    shortLabel: 'Other',
    color: 'text-stone-600 dark:text-stone-400',
  },
}

// GPU icon SVG
const GpuIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="6" width="20" height="12" rx="2" />
    <line x1="6" y1="10" x2="6" y2="14" />
    <line x1="10" y1="10" x2="10" y2="14" />
    <line x1="14" y1="10" x2="14" y2="14" />
    <line x1="18" y1="10" x2="18" y2="14" />
    <circle cx="6" cy="6" r="1" fill="currentColor" />
    <circle cx="18" cy="6" r="1" fill="currentColor" />
  </svg>
)

export function AcceleratorIcon({ type, size = 'md', showLabel = false, count }: AcceleratorIconProps) {
  const config = acceleratorConfig[type]
  if (!config) return null

  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
  }

  return (
    <span className={`inline-flex items-center gap-1 ${config.color}`} title={config.label}>
      <GpuIcon className={sizeClasses[size]} />
      {showLabel && (
        <span className="text-xs font-medium">{config.shortLabel}</span>
      )}
      {count !== undefined && count > 0 && (
        <span className="text-xs font-semibold">×{count}</span>
      )}
    </span>
  )
}

interface AcceleratorSummaryProps {
  summary: Record<string, number>
  size?: 'sm' | 'md'
}

export function AcceleratorSummary({ summary, size = 'md' }: AcceleratorSummaryProps) {
  const entries = Object.entries(summary).filter(([_, count]) => count > 0)

  if (entries.length === 0) {
    return (
      <span className="text-xs text-stone-400 dark:text-stone-500">
        无加速器
      </span>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([type, count]) => (
        <AcceleratorIcon
          key={type}
          type={type as AcceleratorType}
          size={size}
          showLabel={size !== 'sm'}
          count={count}
        />
      ))}
    </div>
  )
}
