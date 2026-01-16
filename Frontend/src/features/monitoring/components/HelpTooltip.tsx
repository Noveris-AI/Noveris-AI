/**
 * Help Tooltip Component
 *
 * Displays help information for metrics in beginner-friendly format
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { HelpCircle, X } from 'lucide-react'
import type { HelpTooltip as HelpTooltipType } from '../api/client'

interface HelpTooltipProps {
  tooltip: HelpTooltipType
}

export function HelpTooltip({ tooltip }: HelpTooltipProps) {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="relative inline-block ml-1">
      <button
        onClick={(e) => {
          e.stopPropagation()
          setIsOpen(!isOpen)
        }}
        className="text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 transition-colors"
      >
        <HelpCircle className="w-4 h-4" />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={(e) => {
              e.stopPropagation()
              setIsOpen(false)
            }}
          />

          {/* Tooltip content */}
          <div
            className="
              absolute left-0 top-6 z-50 w-72
              bg-white dark:bg-stone-800
              border border-stone-200 dark:border-stone-700
              rounded-lg shadow-lg p-4
            "
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setIsOpen(false)}
              className="absolute top-2 right-2 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300"
            >
              <X className="w-4 h-4" />
            </button>

            {/* Description */}
            <p className="text-sm text-stone-700 dark:text-stone-300 mb-3">
              {tooltip.description}
            </p>

            {/* Causes */}
            {tooltip.causes.length > 0 && (
              <div className="mb-3">
                <h4 className="text-xs font-semibold text-stone-500 dark:text-stone-400 uppercase mb-1">
                  {t('monitoring.help.commonCauses')}
                </h4>
                <ul className="text-xs text-stone-600 dark:text-stone-400 space-y-1">
                  {tooltip.causes.map((cause, i) => (
                    <li key={i} className="flex items-start">
                      <span className="text-amber-500 mr-1.5">•</span>
                      {cause}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Actions */}
            {tooltip.actions.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-stone-500 dark:text-stone-400 uppercase mb-1">
                  {t('monitoring.help.suggestedActions')}
                </h4>
                <ul className="text-xs text-stone-600 dark:text-stone-400 space-y-1">
                  {tooltip.actions.map((action, i) => (
                    <li key={i} className="flex items-start">
                      <span className="text-teal-500 mr-1.5">→</span>
                      {action}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
