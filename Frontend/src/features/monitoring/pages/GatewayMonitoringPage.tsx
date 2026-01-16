/**
 * Gateway Monitoring Page
 */

import { useTranslation } from 'react-i18next'
import { useOutletContext } from 'react-router-dom'
import { Network, Activity, AlertTriangle, Clock } from 'lucide-react'

interface ContextType {
  timeRange: string
  displayMode: 'simple' | 'advanced'
}

export function GatewayMonitoringPage() {
  const { t } = useTranslation()
  const { displayMode } = useOutletContext<ContextType>()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
          {t('monitoring.gateway.title')}
        </h2>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
          {t('monitoring.gateway.description')}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <Activity className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.gateway.requestRate')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">--</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <AlertTriangle className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.gateway.errorRate')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">--</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <Clock className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.gateway.p99Latency')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">--</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <Network className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.gateway.activeConnections')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">--</div>
        </div>
      </div>

      <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4 h-64 flex items-center justify-center">
        <p className="text-stone-400">{t('monitoring.gateway.chartPlaceholder')}</p>
      </div>
    </div>
  )
}
