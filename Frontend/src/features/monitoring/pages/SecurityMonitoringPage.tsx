/**
 * Security Monitoring Page
 */

import { useTranslation } from 'react-i18next'
import { Shield, Key, AlertTriangle, FileCheck } from 'lucide-react'

export function SecurityMonitoringPage() {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
          {t('monitoring.security.title')}
        </h2>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
          {t('monitoring.security.description')}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <Key className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.security.sshFailures')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">0</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <AlertTriangle className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.security.anomalies')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">0</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <Shield className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.security.blockedIPs')}</span>
          </div>
          <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">0</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
            <FileCheck className="w-4 h-4 mr-2" />
            <span className="text-xs uppercase">{t('monitoring.security.integrityChecks')}</span>
          </div>
          <div className="text-2xl font-semibold text-emerald-600 dark:text-emerald-400">OK</div>
        </div>
      </div>

      <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4 h-64 flex items-center justify-center">
        <p className="text-stone-400">{t('monitoring.security.chartPlaceholder')}</p>
      </div>
    </div>
  )
}
