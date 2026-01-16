/**
 * Metric Card Component
 *
 * Displays a monitoring metric with status indicator and optional sparkline
 */

import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  HelpCircle,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react'
import { HelpTooltip as HelpTooltipComponent } from './HelpTooltip'
import type { OverviewCard, KeyMetric } from '../api/client'

interface MetricCardProps {
  card: OverviewCard
  onClick?: () => void
}

const statusConfig = {
  ok: {
    color: 'text-emerald-600 dark:text-emerald-400',
    bgColor: 'bg-emerald-50 dark:bg-emerald-900/20',
    borderColor: 'border-emerald-200 dark:border-emerald-800',
    Icon: CheckCircle,
  },
  warning: {
    color: 'text-amber-600 dark:text-amber-400',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    borderColor: 'border-amber-200 dark:border-amber-800',
    Icon: AlertTriangle,
  },
  critical: {
    color: 'text-red-600 dark:text-red-400',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    borderColor: 'border-red-200 dark:border-red-800',
    Icon: XCircle,
  },
  unknown: {
    color: 'text-stone-500 dark:text-stone-400',
    bgColor: 'bg-stone-50 dark:bg-stone-800/50',
    borderColor: 'border-stone-200 dark:border-stone-700',
    Icon: HelpCircle,
  },
}

function formatMetricValue(value: number | string, unit?: string): string {
  if (typeof value === 'string') return value

  if (unit === 'bytes') {
    if (value >= 1e12) return `${(value / 1e12).toFixed(1)} TB`
    if (value >= 1e9) return `${(value / 1e9).toFixed(1)} GB`
    if (value >= 1e6) return `${(value / 1e6).toFixed(1)} MB`
    if (value >= 1e3) return `${(value / 1e3).toFixed(1)} KB`
    return `${value} B`
  }

  if (unit === '%') return `${value.toFixed(1)}%`
  if (unit === 'ms') return `${value.toFixed(0)} ms`
  if (unit === 'req/s') return `${value.toFixed(2)} req/s`

  return `${value}${unit ? ` ${unit}` : ''}`
}

function MiniSparkline({ points }: { points: number[][] }) {
  if (!points || points.length < 2) return null

  const values = points.map(p => p[1])
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1

  const width = 80
  const height = 24
  const padding = 2

  const pathPoints = points.map((point, i) => {
    const x = padding + (i / (points.length - 1)) * (width - 2 * padding)
    const y = height - padding - ((point[1] - min) / range) * (height - 2 * padding)
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
  }).join(' ')

  return (
    <svg width={width} height={height} className="opacity-70">
      <path
        d={pathPoints}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-teal-500"
      />
    </svg>
  )
}

export function MetricCard({ card, onClick }: MetricCardProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const status = statusConfig[card.status]
  const StatusIcon = status.Icon

  const handleClick = () => {
    if (onClick) {
      onClick()
    } else {
      navigate(card.route)
    }
  }

  return (
    <div
      onClick={handleClick}
      className={`
        relative p-4 rounded-lg border cursor-pointer transition-all
        hover:shadow-md hover:border-teal-300 dark:hover:border-teal-700
        ${status.bgColor} ${status.borderColor}
      `}
    >
      {/* Status indicator */}
      <div className="absolute top-3 right-3">
        <StatusIcon className={`w-5 h-5 ${status.color}`} />
      </div>

      {/* Title */}
      <div className="flex items-center mb-3">
        <h3 className="text-sm font-medium text-stone-900 dark:text-stone-100">
          {t(card.title_i18n_key)}
        </h3>
        {card.help_tooltip && (
          <HelpTooltipComponent tooltip={card.help_tooltip} />
        )}
      </div>

      {/* Key metrics */}
      <div className="space-y-2">
        {card.key_metrics.map((metric, index) => (
          <div key={index} className="flex items-center justify-between">
            <span className="text-xs text-stone-500 dark:text-stone-400">
              {t(`monitoring.metrics.${metric.name}`)}
            </span>
            <span className={`text-sm font-semibold ${statusConfig[metric.status].color}`}>
              {formatMetricValue(metric.value, metric.unit)}
            </span>
          </div>
        ))}
      </div>

      {/* Sparkline */}
      {card.sparkline && card.sparkline.points.length > 0 && (
        <div className="mt-3 flex justify-end">
          <MiniSparkline points={card.sparkline.points} />
        </div>
      )}
    </div>
  )
}
