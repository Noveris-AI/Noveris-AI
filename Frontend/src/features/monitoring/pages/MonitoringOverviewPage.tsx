/**
 * Monitoring Overview Page
 *
 * Displays a card grid overview of all monitoring domains
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useOutletContext } from 'react-router-dom'
import { RefreshCw, AlertCircle, CheckCircle } from 'lucide-react'
import { MetricCard } from '../components/MetricCard'
import { getOverview, getDataSourcesHealth } from '../api/client'
import type { OverviewCard } from '../api/client'

interface ContextType {
  timeRange: string
  displayMode: 'simple' | 'advanced'
}

export function MonitoringOverviewPage() {
  const { t } = useTranslation()
  const { timeRange } = useOutletContext<ContextType>()
  const [cards, setCards] = useState<OverviewCard[]>([])
  const [dataSourcesHealth, setDataSourcesHealth] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [overviewData, healthData] = await Promise.all([
        getOverview(timeRange).catch(() => ({ cards: [], data_sources_status: {} })),
        getDataSourcesHealth().catch(() => ({})),
      ])
      setCards(overviewData?.cards || [])
      setDataSourcesHealth(healthData || {})
      setLastUpdated(new Date())
    } catch (err) {
      setError(t('monitoring.overview.error'))
      console.error('Failed to fetch monitoring data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [timeRange])

  const healthySources = Object.values(dataSourcesHealth).filter(s => s === 'ok').length
  const totalSources = Object.keys(dataSourcesHealth).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
            {t('monitoring.overview.title')}
          </h2>
          <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
            {t('monitoring.overview.description')}
          </p>
        </div>
        <div className="flex items-center space-x-4">
          {/* Data sources status */}
          <div className="flex items-center text-sm">
            {healthySources === totalSources ? (
              <CheckCircle className="w-4 h-4 text-emerald-500 mr-1.5" />
            ) : (
              <AlertCircle className="w-4 h-4 text-amber-500 mr-1.5" />
            )}
            <span className="text-stone-600 dark:text-stone-400">
              {t('monitoring.overview.dataSources', { healthy: healthySources, total: totalSources })}
            </span>
          </div>
          {/* Refresh button */}
          <button
            onClick={fetchData}
            disabled={loading}
            className="
              flex items-center px-3 py-1.5 rounded-md text-sm
              bg-stone-100 hover:bg-stone-200 dark:bg-stone-800 dark:hover:bg-stone-700
              text-stone-700 dark:text-stone-300
              disabled:opacity-50 transition-colors
            "
          >
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            {t('monitoring.overview.refresh')}
          </button>
        </div>
      </div>

      {/* Last updated */}
      {lastUpdated && (
        <p className="text-xs text-stone-400 dark:text-stone-500">
          {t('monitoring.overview.lastUpdated', {
            time: lastUpdated.toLocaleTimeString(),
          })}
        </p>
      )}

      {/* Error message */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 mr-2" />
            <span className="text-red-700 dark:text-red-300">{error}</span>
          </div>
        </div>
      )}

      {/* Card grid */}
      {loading && cards.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div
              key={i}
              className="h-40 bg-stone-100 dark:bg-stone-800 rounded-lg animate-pulse"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {cards.map((card) => (
            <MetricCard key={card.key} card={card} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && cards.length === 0 && !error && (
        <div className="text-center py-12">
          <p className="text-stone-500 dark:text-stone-400">
            {t('monitoring.overview.noData')}
          </p>
        </div>
      )}
    </div>
  )
}
