/**
 * Models Monitoring Page
 *
 * Displays model service metrics
 */

import { useTranslation } from 'react-i18next'
import { useOutletContext } from 'react-router-dom'
import { Bot, Clock, Zap, TrendingUp } from 'lucide-react'

interface ContextType {
  timeRange: string
  displayMode: 'simple' | 'advanced'
}

export function ModelsMonitoringPage() {
  const { t } = useTranslation()
  const { displayMode } = useOutletContext<ContextType>()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
          {t('monitoring.models.title')}
        </h2>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
          {t('monitoring.models.description')}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <Bot className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.models.instances')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">--</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <Clock className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.models.p99Latency')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">--</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <Zap className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.models.throughput')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">--</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <TrendingUp className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.models.successRate')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">--</div>
        </div>
      </div>

      {displayMode === 'advanced' && (
        <div className="bg-stone-900 rounded-lg p-4">
          <h4 className="text-xs font-semibold text-stone-400 uppercase mb-2">
            {t('monitoring.models.promql')}
          </h4>
          <code className="text-xs text-teal-400 font-mono">
            histogram_quantile(0.99, sum(rate(vllm:e2e_request_latency_seconds_bucket[5m])) by (le))
          </code>
        </div>
      )}

      <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4 h-64 flex items-center justify-center">
        <p className="text-stone-400">{t('monitoring.models.chartPlaceholder')}</p>
      </div>
    </div>
  )
}
