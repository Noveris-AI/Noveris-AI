/**
 * Deployment Detail Page
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { deploymentClient } from '../api/deploymentClient'
import type { DeploymentDetail, LogLine, DeploymentLog } from '../api/deploymentTypes'
import {
  DeploymentStatusBadge,
  HealthStatusBadge,
  FrameworkBadge,
} from '../components/StatusBadge'
import { EnvTableDisplay } from '../components/EnvTable'
import { ArgsTableDisplay } from '../components/ArgsTable'
import { DeviceDisplay } from '../components/DeviceSelector'
import { DeploymentLogViewer, ServiceLogViewer } from '../components/LogViewer'

export function DeploymentDetailPage() {
  const { deploymentId } = useParams<{ deploymentId: string }>()
  const navigate = useNavigate()

  // State
  const [deployment, setDeployment] = useState<DeploymentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  // Logs state
  const [activeTab, setActiveTab] = useState<'overview' | 'logs' | 'service-logs'>('overview')
  const [deploymentLogs, setDeploymentLogs] = useState<DeploymentLog[]>([])
  const [serviceLogs, setServiceLogs] = useState<LogLine[]>([])
  const [logsLoading, setLogsLoading] = useState(false)

  // Delete confirmation
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // Load deployment
  const fetchDeployment = async () => {
    if (!deploymentId) return

    try {
      const data = await deploymentClient.getDeployment(deploymentId)
      setDeployment(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载部署详情失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDeployment()
  }, [deploymentId])

  // Load logs when tab changes
  useEffect(() => {
    if (!deploymentId) return

    const fetchLogs = async () => {
      setLogsLoading(true)
      try {
        if (activeTab === 'logs') {
          const response = await deploymentClient.getDeploymentLogs(deploymentId, { page_size: 100 })
          setDeploymentLogs(response.logs)
        } else if (activeTab === 'service-logs') {
          const response = await deploymentClient.getServiceLogs(deploymentId, { lines: 500 })
          setServiceLogs(response.lines)
        }
      } catch (err) {
        console.error('Failed to fetch logs:', err)
      } finally {
        setLogsLoading(false)
      }
    }

    if (activeTab !== 'overview') {
      fetchLogs()
    }
  }, [deploymentId, activeTab])

  // Auto-refresh deployment status
  useEffect(() => {
    if (!deployment) return

    const isActiveStatus = ['PENDING', 'DOWNLOADING', 'INSTALLING', 'STARTING', 'DELETING'].includes(deployment.status)
    if (!isActiveStatus) return

    const interval = setInterval(fetchDeployment, 5000)
    return () => clearInterval(interval)
  }, [deployment?.status])

  // Actions
  const handleAction = async (action: 'start' | 'stop' | 'restart') => {
    if (!deploymentId) return

    setActionLoading(action)
    try {
      if (action === 'start') {
        await deploymentClient.startDeployment(deploymentId)
      } else if (action === 'stop') {
        await deploymentClient.stopDeployment(deploymentId)
      } else {
        await deploymentClient.restartDeployment(deploymentId)
      }
      await fetchDeployment()
    } catch (err) {
      console.error(`Failed to ${action} deployment:`, err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async () => {
    if (!deploymentId) return

    setDeleting(true)
    try {
      await deploymentClient.deleteDeployment(deploymentId)
      navigate('/dashboard/deployment')
    } catch (err) {
      console.error('Failed to delete deployment:', err)
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600 mx-auto"></div>
          <p className="mt-2 text-stone-600 dark:text-stone-400">加载中...</p>
        </div>
      </div>
    )
  }

  if (error || !deployment) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400">{error || '部署不存在'}</p>
          <button
            onClick={() => navigate('/dashboard/deployment')}
            className="mt-4 px-4 py-2 bg-teal-600 text-white rounded-lg"
          >
            返回列表
          </button>
        </div>
      </div>
    )
  }

  const isRunning = deployment.status === 'RUNNING'
  const isStopped = deployment.status === 'STOPPED' || deployment.status === 'FAILED'
  const isActionable = !['PENDING', 'DOWNLOADING', 'INSTALLING', 'STARTING', 'DELETING'].includes(deployment.status)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => navigate('/dashboard/deployment')}
            className="flex items-center text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 mb-2"
          >
            <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            返回部署列表
          </button>
          <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            {deployment.display_name || deployment.name}
          </h1>
          <div className="flex items-center gap-3 mt-2">
            <DeploymentStatusBadge status={deployment.status} />
            {isRunning && <HealthStatusBadge status={deployment.health_status} />}
            <FrameworkBadge framework={deployment.framework} />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {isActionable && isStopped && (
            <button
              onClick={() => handleAction('start')}
              disabled={actionLoading !== null}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg flex items-center gap-2 disabled:opacity-50"
            >
              {actionLoading === 'start' && (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              )}
              启动
            </button>
          )}
          {isActionable && isRunning && (
            <>
              <button
                onClick={() => handleAction('restart')}
                disabled={actionLoading !== null}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg flex items-center gap-2 disabled:opacity-50"
              >
                {actionLoading === 'restart' && (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                )}
                重启
              </button>
              <button
                onClick={() => handleAction('stop')}
                disabled={actionLoading !== null}
                className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg flex items-center gap-2 disabled:opacity-50"
              >
                {actionLoading === 'stop' && (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                )}
                停止
              </button>
            </>
          )}
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg"
          >
            删除
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-stone-200 dark:border-stone-700">
        <div className="flex gap-6">
          {(['overview', 'logs', 'service-logs'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? 'border-teal-600 text-teal-600 dark:text-teal-400'
                  : 'border-transparent text-stone-500 hover:text-stone-700 dark:hover:text-stone-300'
              }`}
            >
              {tab === 'overview' && '概览'}
              {tab === 'logs' && '部署日志'}
              {tab === 'service-logs' && '服务日志'}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Basic Info */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">基本信息</h2>
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-sm text-stone-500">名称</dt>
                <dd className="text-sm text-stone-900 dark:text-stone-100 font-mono">{deployment.name}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-stone-500">框架</dt>
                <dd><FrameworkBadge framework={deployment.framework} /></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-stone-500">模型</dt>
                <dd className="text-sm text-stone-900 dark:text-stone-100 font-mono truncate max-w-xs">
                  {deployment.model_repo_id}
                </dd>
              </div>
              {deployment.model_revision && (
                <div className="flex justify-between">
                  <dt className="text-sm text-stone-500">版本</dt>
                  <dd className="text-sm text-stone-900 dark:text-stone-100">{deployment.model_revision}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-sm text-stone-500">模型来源</dt>
                <dd className="text-sm text-stone-900 dark:text-stone-100">{deployment.model_source}</dd>
              </div>
              {deployment.description && (
                <div>
                  <dt className="text-sm text-stone-500 mb-1">描述</dt>
                  <dd className="text-sm text-stone-700 dark:text-stone-300">{deployment.description}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Node Info */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">节点信息</h2>
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-sm text-stone-500">节点</dt>
                <dd className="text-sm text-stone-900 dark:text-stone-100">
                  {deployment.node_name || deployment.node_host || '未知'}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-stone-500">服务地址</dt>
                <dd className="text-sm text-stone-900 dark:text-stone-100 font-mono">
                  {deployment.host}:{deployment.port}
                </dd>
              </div>
              <div className="flex justify-between items-start">
                <dt className="text-sm text-stone-500">GPU 设备</dt>
                <dd><DeviceDisplay devices={deployment.gpu_devices} /></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-stone-500">张量并行度</dt>
                <dd className="text-sm text-stone-900 dark:text-stone-100">{deployment.tensor_parallel_size}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-stone-500">显存利用率</dt>
                <dd className="text-sm text-stone-900 dark:text-stone-100">
                  {(deployment.gpu_memory_utilization * 100).toFixed(0)}%
                </dd>
              </div>
            </dl>
          </div>

          {/* API Endpoints */}
          {deployment.endpoints && Object.keys(deployment.endpoints).length > 0 && (
            <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
              <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">API 端点</h2>
              <dl className="space-y-3">
                {Object.entries(deployment.endpoints).map(([key, url]) => (
                  <div key={key}>
                    <dt className="text-sm text-stone-500 mb-1">{key}</dt>
                    <dd className="text-sm font-mono bg-stone-50 dark:bg-stone-900 p-2 rounded break-all">
                      {url}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* Error Info */}
          {deployment.error_message && (
            <div className="bg-red-50 dark:bg-red-900/20 rounded-xl border border-red-200 dark:border-red-800 p-6">
              <h2 className="text-lg font-semibold text-red-800 dark:text-red-200 mb-4">错误信息</h2>
              <p className="text-sm text-red-700 dark:text-red-300 whitespace-pre-wrap">
                {deployment.error_message}
              </p>
              {deployment.error_detail && (
                <details className="mt-3">
                  <summary className="text-sm text-red-600 cursor-pointer">查看详细信息</summary>
                  <pre className="mt-2 text-xs bg-red-100 dark:bg-red-950 p-3 rounded overflow-auto max-h-48">
                    {deployment.error_detail}
                  </pre>
                </details>
              )}
            </div>
          )}

          {/* Environment Variables */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">环境变量</h2>
            <EnvTableDisplay entries={deployment.env_table} />
          </div>

          {/* CLI Arguments */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">启动参数</h2>
            <ArgsTableDisplay entries={deployment.args_table} />
          </div>

          {/* Timestamps */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">时间信息</h2>
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-sm text-stone-500">创建时间</dt>
                <dd className="text-sm text-stone-900 dark:text-stone-100">
                  {new Date(deployment.created_at).toLocaleString()}
                </dd>
              </div>
              {deployment.started_at && (
                <div className="flex justify-between">
                  <dt className="text-sm text-stone-500">启动时间</dt>
                  <dd className="text-sm text-stone-900 dark:text-stone-100">
                    {new Date(deployment.started_at).toLocaleString()}
                  </dd>
                </div>
              )}
              {deployment.stopped_at && (
                <div className="flex justify-between">
                  <dt className="text-sm text-stone-500">停止时间</dt>
                  <dd className="text-sm text-stone-900 dark:text-stone-100">
                    {new Date(deployment.stopped_at).toLocaleString()}
                  </dd>
                </div>
              )}
              {deployment.last_health_check_at && (
                <div className="flex justify-between">
                  <dt className="text-sm text-stone-500">最后健康检查</dt>
                  <dd className="text-sm text-stone-900 dark:text-stone-100">
                    {new Date(deployment.last_health_check_at).toLocaleString()}
                  </dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-sm text-stone-500">创建者</dt>
                <dd className="text-sm text-stone-900 dark:text-stone-100">
                  {deployment.created_by_email || deployment.created_by}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      )}

      {activeTab === 'logs' && (
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 h-[600px]">
          <DeploymentLogViewer
            logs={deploymentLogs}
            loading={logsLoading}
            onRefresh={() => {
              setActiveTab('overview')
              setTimeout(() => setActiveTab('logs'), 0)
            }}
          />
        </div>
      )}

      {activeTab === 'service-logs' && (
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 h-[600px]">
          <ServiceLogViewer
            lines={serviceLogs}
            loading={logsLoading}
            onRefresh={() => {
              setActiveTab('overview')
              setTimeout(() => setActiveTab('service-logs'), 0)
            }}
          />
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-stone-800 rounded-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">
              确认删除部署
            </h3>
            <p className="text-stone-600 dark:text-stone-400 mb-6">
              确定要删除部署 <strong>{deployment.name}</strong> 吗？此操作将停止服务并删除所有相关文件，无法撤销。
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-700"
              >
                取消
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg flex items-center gap-2 disabled:opacity-50"
              >
                {deleting && (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                )}
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
