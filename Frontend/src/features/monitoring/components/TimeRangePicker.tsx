/**
 * Time Range Picker Component
 *
 * Allows selection of predefined time ranges for monitoring queries
 */

import { useTranslation } from 'react-i18next'
import { Clock } from 'lucide-react'

interface TimeRangePickerProps {
  value: string
  onChange: (value: string) => void
}

const timeRanges = [
  { value: '15m', label: 'monitoring.timeRange.15m' },
  { value: '1h', label: 'monitoring.timeRange.1h' },
  { value: '6h', label: 'monitoring.timeRange.6h' },
  { value: '24h', label: 'monitoring.timeRange.24h' },
  { value: '7d', label: 'monitoring.timeRange.7d' },
  { value: '30d', label: 'monitoring.timeRange.30d' },
]

export function TimeRangePicker({ value, onChange }: TimeRangePickerProps) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center space-x-2">
      <Clock className="w-4 h-4 text-stone-500 dark:text-stone-400" />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="
          text-sm bg-white dark:bg-stone-800
          border border-stone-300 dark:border-stone-600
          rounded-md px-2 py-1
          text-stone-900 dark:text-stone-100
          focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500
        "
      >
        {timeRanges.map((range) => (
          <option key={range.value} value={range.value}>
            {t(range.label)}
          </option>
        ))}
      </select>
    </div>
  )
}
