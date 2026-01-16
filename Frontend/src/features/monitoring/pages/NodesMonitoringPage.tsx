/**
 * Nodes Monitoring Page
 *
 * Displays detailed node metrics and status
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useOutletContext } from 'react-router-dom'
import { Server, Activity, HardDrive, Cpu, MemoryStick } from 'lucide-react'
import { getNodes, getNodeMetrics } from '../api/client'
import type { NodeSummary } from '../api/client'

interface ContextType {
  timeRange: string
  displayMode: 'simple' | 'advanced'
}

export function NodesMonitoringPage() {
  const { t } = useTranslation()
  const { timeRange, displayMode } = useOutletContext<ContextType>()
  const [nodes, setNodes] = useState<NodeSummary[]>([])
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchNodes() {
      setLoading(true)
      try {
        const data = await getNodes()
        setNodes(data.nodes)
        if (data.nodes.length > 0 && !selectedNode) {
          setSelectedNode(data.nodes[0].instance)
        }
      } catch (err) {
        console.error('Failed to fetch nodes:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchNodes()
  }, [])

  useEffect(() => {
    async function fetchMetrics() {
      if (!selectedNode) return
      try {
        const data = await getNodeMetrics(selectedNode, timeRange)
        setMetrics(data.metrics)
      } catch (err) {
        console.error('Failed to fetch node metrics:', err)
      }
    }
    fetchMetrics()
  }, [selectedNode, timeRange])

  const statusColors: Record<string, string> = {
    ok: 'bg-emerald-500',
    warning: 'bg-amber-500',
    critical: 'bg-red-500',
    unknown: 'bg-stone-400',
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
          {t('monitoring.nodes.title')}
        </h2>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
          {t('monitoring.nodes.description')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Node list */}
        <div className="lg:col-span-1">
          <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700">
            <div className="p-4 border-b border-stone-200 dark:border-stone-700">
              <h3 className="font-medium text-stone-900 dark:text-stone-100">
                {t('monitoring.nodes.list')}
              </h3>
            </div>
            <div className="divide-y divide-stone-200 dark:divide-stone-700">
              {loading ? (
                <div className="p-4 text-center text-stone-500">
                  {t('common.loading')}
                </div>
              ) : nodes.length === 0 ? (
                <div className="p-4 text-center text-stone-500">
                  {t('monitoring.nodes.noNodes')}
                </div>
              ) : (
                nodes.map((node) => (
                  <button
                    key={node.instance}
                    onClick={() => setSelectedNode(node.instance)}
                    className={`
                      w-full p-3 text-left transition-colors
                      ${selectedNode === node.instance
                        ? 'bg-teal-50 dark:bg-teal-900/20'
                        : 'hover:bg-stone-50 dark:hover:bg-stone-700/50'
                      }
                    `}
                  >
                    <div className="flex items-center">
                      <div className={`w-2 h-2 rounded-full mr-3 ${statusColors[node.status]}`} />
                      <div>
                        <div className="text-sm font-medium text-stone-900 dark:text-stone-100">
                          {node.hostname}
                        </div>
                        <div className="text-xs text-stone-500 dark:text-stone-400">
                          {node.instance}
                        </div>
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Metrics display */}
        <div className="lg:col-span-3">
          {selectedNode ? (
            <div className="space-y-4">
              {/* Summary cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
                  <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
                    <Cpu className="w-4 h-4 mr-2" />
                    <span className="text-xs uppercase">{t('monitoring.nodes.cpu')}</span>
                  </div>
                  <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                    {metrics?.cpu ? `${metrics.cpu[0]?.values?.slice(-1)?.[0]?.[1] || 0}%` : '--'}
                  </div>
                </div>
                <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
                  <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
                    <MemoryStick className="w-4 h-4 mr-2" />
                    <span className="text-xs uppercase">{t('monitoring.nodes.memory')}</span>
                  </div>
                  <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                    {metrics?.memory ? `${metrics.memory[0]?.values?.slice(-1)?.[0]?.[1] || 0}%` : '--'}
                  </div>
                </div>
                <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
                  <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
                    <HardDrive className="w-4 h-4 mr-2" />
                    <span className="text-xs uppercase">{t('monitoring.nodes.disk')}</span>
                  </div>
                  <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                    {metrics?.disk ? `${metrics.disk[0]?.values?.slice(-1)?.[0]?.[1] || 0}%` : '--'}
                  </div>
                </div>
                <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
                  <div className="flex items-center text-stone-500 dark:text-stone-400 mb-2">
                    <Activity className="w-4 h-4 mr-2" />
                    <span className="text-xs uppercase">{t('monitoring.nodes.load')}</span>
                  </div>
                  <div className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                    {metrics?.load ? metrics.load[0]?.values?.slice(-1)?.[0]?.[1] || '--' : '--'}
                  </div>
                </div>
              </div>

              {/* Advanced mode: Show PromQL */}
              {displayMode === 'advanced' && (
                <div className="bg-stone-900 rounded-lg p-4">
                  <h4 className="text-xs font-semibold text-stone-400 uppercase mb-2">
                    {t('monitoring.nodes.promql')}
                  </h4>
                  <code className="text-xs text-teal-400 font-mono">
                    {`100 - (avg by(instance)(irate(node_cpu_seconds_total{instance="${selectedNode}",mode="idle"}[5m])) * 100)`}
                  </code>
                </div>
              )}

              {/* Placeholder for charts */}
              <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4 h-64 flex items-center justify-center">
                <p className="text-stone-400">{t('monitoring.nodes.chartPlaceholder')}</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-stone-500">
              {t('monitoring.nodes.selectNode')}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
