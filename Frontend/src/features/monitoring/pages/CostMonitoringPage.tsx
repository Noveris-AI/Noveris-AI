/**
 * Cost Monitoring Page
 */

import { useTranslation } from 'react-i18next'
import { DollarSign, TrendingUp, AlertCircle, PieChart } from 'lucide-react'

export function CostMonitoringPage() {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
          {t('monitoring.cost.title')}
        </h2>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
          {t('monitoring.cost.description')}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <DollarSign className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.cost.currentSpending')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">$0.00</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <TrendingUp className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.cost.projectedCost')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">$0.00</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <AlertCircle className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.cost.budgetRemaining')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">--</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <PieChart className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.cost.topConsumer')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">--</div>
        </div>
      </div>

      <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4 h-64 flex items-center justify-center">
        <p className="text-stone-400">{t('monitoring.cost.chartPlaceholder')}</p>
      </div>
    </div>
  )
}
