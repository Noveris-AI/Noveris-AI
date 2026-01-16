/**
 * Mode Toggle Component
 *
 * Switches between Simple and Advanced display modes
 */

import { useTranslation } from 'react-i18next'
import { Eye, Code } from 'lucide-react'

interface ModeToggleProps {
  mode: 'simple' | 'advanced'
  onChange: (mode: 'simple' | 'advanced') => void
}

export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center bg-stone-100 dark:bg-stone-800 rounded-md p-0.5">
      <button
        onClick={() => onChange('simple')}
        className={`
          flex items-center px-3 py-1 rounded text-sm font-medium transition-colors
          ${mode === 'simple'
            ? 'bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 shadow-sm'
            : 'text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100'
          }
        `}
      >
        <Eye className="w-4 h-4 mr-1.5" />
        {t('monitoring.mode.simple')}
      </button>
      <button
        onClick={() => onChange('advanced')}
        className={`
          flex items-center px-3 py-1 rounded text-sm font-medium transition-colors
          ${mode === 'advanced'
            ? 'bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 shadow-sm'
            : 'text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100'
          }
        `}
      >
        <Code className="w-4 h-4 mr-1.5" />
        {t('monitoring.mode.advanced')}
      </button>
    </div>
  )
}
