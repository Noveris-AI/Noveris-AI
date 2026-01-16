/**
 * Accelerators Monitoring Page
 *
 * Displays GPU/NPU device metrics
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useOutletContext } from 'react-router-dom'
import { Cpu, Thermometer, Zap, Database } from 'lucide-react'
import { getAccelerators, getAcceleratorMetrics } from '../api/client'
import type { AcceleratorSummary } from '../api/client'

interface ContextType {
  timeRange: string
  displayMode: 'simple' | 'advanced'
}

export function AcceleratorsMonitoringPage() {
  const { t } = useTranslation()
  const { timeRange, displayMode } = useOutletContext<ContextType>()
  const [accelerators, setAccelerators] = useState<AcceleratorSummary[]>([])
  const [selectedDevice, setSelectedDevice] = useState<{ nodeId: string; deviceId: string } | null>(null)
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchAccelerators() {
      setLoading(true)
      try {
        const data = await getAccelerators()
        setAccelerators(data.accelerators)
        if (data.accelerators.length > 0 && !selectedDevice) {
          setSelectedDevice({
            nodeId: data.accelerators[0].hostname,
            deviceId: data.accelerators[0].device_id,
          })
        }
      } catch (err) {
        console.error('Failed to fetch accelerators:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchAccelerators()
  }, [])

  useEffect(() => {
    async function fetchMetrics() {
      if (!selectedDevice) return
      try {
        const data = await getAcceleratorMetrics(
          selectedDevice.nodeId,
          selectedDevice.deviceId,
          timeRange
        )
        setMetrics(data.metrics)
      } catch (err) {
        console.error('Failed to fetch accelerator metrics:', err)
      }
    }
    fetchMetrics()
  }, [selectedDevice, timeRange])

  const vendorColors: Record<string, string> = {
    nvidia: 'bg-green-500',
    huawei_ascend: 'bg-red-500',
    amd: 'bg-orange-500',
    intel: 'bg-blue-500',
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
          {t('monitoring.accelerators.title')}
        </h2>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
          {t('monitoring.accelerators.description')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Device list */}
        <div className="lg:col-span-1">
          <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700">
            <div className="p-4 border-b border-stone-200 dark:border-stone-700">
              <h3 className="font-medium text-stone-900 dark:text-stone-100">
                {t('monitoring.accelerators.devices')}
              </h3>
            </div>
            <div className="divide-y divide-stone-200 dark:divide-stone-700">
              {loading ? (
                <div className="p-4 text-center text-stone-500">
                  {t('common.loading')}
                </div>
              ) : accelerators.length === 0 ? (
                <div className="p-4 text-center text-stone-500">
                  {t('monitoring.accelerators.noDevices')}
                </div>
              ) : (
                accelerators.map((acc, index) => (
                  <button
                    key={`${acc.hostname}-${acc.device_id}`}
                    onClick={() => setSelectedDevice({
                      nodeId: acc.hostname,
                      deviceId: acc.device_id,
                    })}
                    className={`
                      w-full p-3 text-left transition-colors
                      ${selectedDevice?.nodeId === acc.hostname && selectedDevice?.deviceId === acc.device_id
                        ? 'bg-teal-50 dark:bg-teal-900/20'
                        : 'hover:bg-stone-50 dark:hover:bg-stone-700/50'
                      }
                    `}
                  >
                    <div className="flex items-center">
                      <div className={`w-2 h-2 rounded-full mr-3 ${vendorColors[acc.vendor] || 'bg-stone-400'}`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-stone-900 dark:text-stone-100 truncate">
                          {acc.model}
                        </div>
                        <div className="text-xs text-stone-500 dark:text-stone-400">
                          {acc.hostname} • GPU {acc.device_id}
                        </div>
                      </div>
                      {acc.temperature && (
                        <span className={`text-xs font-medium ${
                          acc.temperature > 80 ? 'text-red-600' :
                          acc.temperature > 70 ? 'text-amber-600' :
                          'text-stone-600'
                        }`}>
                          {acc.temperature}°C
                        </span>
                      )}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Metrics display */}
        <div className="lg:col-span-3">
          {selectedDevice ? (
            <div className="space-y-4">
              {/* Summary cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
                  <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
                    <Thermometer className="w-4 h-4 mr-2" />
                    <span className="text-xs uppercase">{t('monitoring.accelerators.temperature')}</span>
                  </div>
                  <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                    {metrics?.temperature ? `${metrics.temperature[0]?.values?.slice(-1)?.[0]?.[1] || '--'}°C` : '--'}
                  </div>
                </div>
                <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
                  <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
                    <Zap className="w-4 h-4 mr-2" />
                    <span className="text-xs uppercase">{t('monitoring.accelerators.power')}</span>
                  </div>
                  <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                    {metrics?.power ? `${metrics.power[0]?.values?.slice(-1)?.[0]?.[1] || '--'}W` : '--'}
                  </div>
                </div>
                <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
                  <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
                    <Database className="w-4 h-4 mr-2" />
                    <span className="text-xs uppercase">{t('monitoring.accelerators.memory')}</span>
                  </div>
                  <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                    {metrics?.memory_used ? `${(metrics.memory_used[0]?.values?.slice(-1)?.[0]?.[1] / 1024).toFixed(1) || '--'} GB` : '--'}
                  </div>
                </div>
                <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
                  <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
                    <Cpu className="w-4 h-4 mr-2" />
                    <span className="text-xs uppercase">{t('monitoring.accelerators.utilization')}</span>
                  </div>
                  <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                    {metrics?.utilization ? `${metrics.utilization[0]?.values?.slice(-1)?.[0]?.[1] || '--'}%` : '--'}
                  </div>
                </div>
              </div>

              {/* Advanced mode: Show PromQL */}
              {displayMode === 'advanced' && (
                <div className="bg-stone-900 rounded-lg p-4">
                  <h4 className="text-xs font-semibold text-stone-400 uppercase mb-2">
                    {t('monitoring.accelerators.promql')}
                  </h4>
                  <code className="text-xs text-teal-400 font-mono">
                    {`DCGM_FI_DEV_GPU_TEMP{Hostname="${selectedDevice.nodeId}",gpu="${selectedDevice.deviceId}"}`}
                  </code>
                </div>
              )}

              {/* Placeholder for charts */}
              <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4 h-64 flex items-center justify-center">
                <p className="text-stone-400">{t('monitoring.accelerators.chartPlaceholder')}</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-stone-500">
              {t('monitoring.accelerators.selectDevice')}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
