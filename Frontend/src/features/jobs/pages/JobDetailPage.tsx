/**
 * Job Detail Page with Log Viewer
 */

import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { nodeManagementClient } from '../../nodes/api/nodeManagementClient'
import type { JobRunDetail, JobRunEvent } from '../../nodes/api/nodeManagementTypes'
import { JobStatusBadge, NodeStatusBadge } from '../../nodes/components/StatusBadge'

export function JobDetailPage() {
  const { t } = useTranslation()
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()

  // State
  const [job, setJob] = useState<JobRunDetail | null>(null)
  const [events, setEvents] = useState<JobRunEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [canceling, setCanceling] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)

  const logContainerRef = useRef<HTMLDivElement>(null)
  const pollingRef = useRef<NodeJS.Timer | null>(null)

  // Fetch job details
  const fetchJob = async () => {
    if (!jobId) return

    try {
      const [jobData, eventsData] = await Promise.all([
        nodeManagementClient.getJobRun(jobId),
        nodeManagementClient.getJobRunEvents(jobId),
      ])

      setJob(jobData)
      setEvents(eventsData.events)
      setError(null)

      // Auto-scroll to bottom
      if (autoScroll && logContainerRef.current) {
        logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
      }

      return jobData
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
      return null
    } finally {
      setLoading(false)
    }
  }

  // Initial load
  useEffect(() => {
    fetchJob()
  }, [jobId])

  // Polling for running jobs
  useEffect(() => {
    if (job?.status === 'RUNNING' || job?.status === 'PENDING') {
      pollingRef.current = setInterval(() => {
        fetchJob()
      }, 3000)
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [job?.status])

  // Handle cancel
  const handleCancel = async () => {
    if (!jobId) return

    setCanceling(true)
    try {
      await nodeManagementClient.cancelJobRun(jobId, '用户取消')
      await fetchJob()
    } catch (err) {
      console.error('Failed to cancel job:', err)
    } finally {
      setCanceling(false)
    }
  }

  // Format helpers
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleString('zh-CN')
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-'
    if (seconds < 60) return `${seconds}秒`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}分${seconds % 60}秒`
    return `${Math.floor(seconds / 3600)}时${Math.floor((seconds % 3600) / 60)}分`
  }

  // Get event color based on type/status
  const getEventColor = (event: JobRunEvent): string => {
    if (event.event_type === 'runner_on_failed') return 'text-red-500'
    if (event.event_type === 'runner_on_unreachable') return 'text-amber-500'
    if (event.event_type === 'runner_on_skipped') return 'text-stone-400'
    if (event.event_type === 'runner_on_ok' && event.payload?.changed) return 'text-amber-500'
    if (event.event_type === 'runner_on_ok') return 'text-green-500'
    if (event.event_type === 'playbook_on_task_start') return 'text-blue-500'
    if (event.event_type === 'playbook_on_play_start') return 'text-purple-500'
    return 'text-stone-600 dark:text-stone-400'
  }

  // Format event for display
  const formatEvent = (event: JobRunEvent): string => {
    const payload = event.payload || {}
    const eventData = payload.event_data || {}

    switch (event.event_type) {
      case 'playbook_on_play_start':
        return `PLAY [${eventData.play || 'unnamed'}]`
      case 'playbook_on_task_start':
        return `TASK [${eventData.task || 'unnamed'}]`
      case 'runner_on_ok':
        return `ok: [${event.hostname || eventData.host || 'unknown'}]${payload.changed ? ' => changed' : ''}`
      case 'runner_on_failed':
        return `fatal: [${event.hostname || eventData.host || 'unknown'}]: ${eventData.res?.msg || 'FAILED'}`
      case 'runner_on_skipped':
        return `skipping: [${event.hostname || eventData.host || 'unknown'}]`
      case 'runner_on_unreachable':
        return `fatal: [${event.hostname || eventData.host || 'unknown'}]: UNREACHABLE`
      case 'playbook_on_stats':
        return 'PLAY RECAP'
      default:
        return event.event_type
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

  if (error || !job) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <svg className="w-16 h-16 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">
            {error || '任务不存在'}
          </h3>
          <button
            onClick={() => navigate('/dashboard/jobs')}
            className="text-teal-600 hover:text-teal-700 dark:text-teal-400"
          >
            返回任务列表
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/dashboard/jobs" className="hover:text-teal-600 dark:hover:text-teal-400">
          任务中心
        </Link>
        <span>/</span>
        <span className="text-stone-900 dark:text-stone-100 truncate">
          {job.template_name || job.id.slice(0, 8)}
        </span>
      </nav>

      {/* Header */}
      <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
                {job.template_name || '未知模板'}
              </h1>
              <JobStatusBadge status={job.status} />
            </div>
            <p className="text-sm text-stone-500 dark:text-stone-400 font-mono">
              ID: {job.id}
            </p>
          </div>

          {(job.status === 'RUNNING' || job.status === 'PENDING') && (
            <button
              onClick={handleCancel}
              disabled={canceling}
              className="px-4 py-2 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {canceling ? (
                <div className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              取消执行
            </button>
          )}
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-6">
          <div className="bg-stone-50 dark:bg-stone-700/50 rounded-lg p-3">
            <p className="text-xs text-stone-500 dark:text-stone-400">目标节点</p>
            <p className="text-lg font-semibold text-stone-900 dark:text-stone-100">{job.node_count}</p>
          </div>
          <div className="bg-stone-50 dark:bg-stone-700/50 rounded-lg p-3">
            <p className="text-xs text-stone-500 dark:text-stone-400">耗时</p>
            <p className="text-lg font-semibold text-stone-900 dark:text-stone-100">
              {formatDuration(job.duration_seconds)}
            </p>
          </div>
          {job.summary && (
            <>
              <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
                <p className="text-xs text-green-600 dark:text-green-400">成功</p>
                <p className="text-lg font-semibold text-green-700 dark:text-green-300">
                  {job.summary.ok || 0}
                </p>
              </div>
              <div className="bg-amber-50 dark:bg-amber-900/20 rounded-lg p-3">
                <p className="text-xs text-amber-600 dark:text-amber-400">变更</p>
                <p className="text-lg font-semibold text-amber-700 dark:text-amber-300">
                  {job.summary.changed || 0}
                </p>
              </div>
              <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
                <p className="text-xs text-red-600 dark:text-red-400">失败</p>
                <p className="text-lg font-semibold text-red-700 dark:text-red-300">
                  {job.summary.failed || 0}
                </p>
              </div>
            </>
          )}
        </div>

        {/* Error Message */}
        {job.error_message && (
          <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-700 dark:text-red-300 whitespace-pre-wrap">
              {job.error_message}
            </p>
          </div>
        )}
      </div>

      {/* Info & Logs Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sidebar Info */}
        <div className="space-y-6">
          {/* Metadata */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">任务信息</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">创建时间</dt>
                <dd className="text-stone-900 dark:text-stone-100">{formatDate(job.created_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">开始时间</dt>
                <dd className="text-stone-900 dark:text-stone-100">{formatDate(job.started_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">完成时间</dt>
                <dd className="text-stone-900 dark:text-stone-100">{formatDate(job.finished_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">执行人</dt>
                <dd className="text-stone-900 dark:text-stone-100">{job.created_by_email || '-'}</dd>
              </div>
              {job.worker_id && (
                <div className="flex justify-between">
                  <dt className="text-stone-500 dark:text-stone-400">Worker</dt>
                  <dd className="text-stone-900 dark:text-stone-100 font-mono text-xs">{job.worker_id}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Target Nodes */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">目标节点</h3>
            {job.nodes.length > 0 ? (
              <div className="space-y-2">
                {job.nodes.map((node) => (
                  <Link
                    key={node.id}
                    to={`/dashboard/nodes/${node.id}`}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700/50 transition-colors"
                  >
                    <span className="text-sm text-stone-900 dark:text-stone-100">
                      {node.display_name || node.name}
                    </span>
                    <NodeStatusBadge status={node.status} size="sm" />
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-stone-500 dark:text-stone-400">无节点信息</p>
            )}
          </div>
        </div>

        {/* Log Viewer */}
        <div className="lg:col-span-2 bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700">
          <div className="p-4 border-b border-stone-200 dark:border-stone-700 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100">执行日志</h3>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-stone-600 dark:text-stone-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                  className="w-4 h-4 text-teal-600 focus:ring-teal-500 rounded"
                />
                自动滚动
              </label>
              {(job.status === 'RUNNING' || job.status === 'PENDING') && (
                <span className="flex items-center gap-1 text-sm text-teal-600 dark:text-teal-400">
                  <div className="w-2 h-2 bg-teal-500 rounded-full animate-pulse" />
                  实时更新中
                </span>
              )}
            </div>
          </div>
          <div
            ref={logContainerRef}
            className="p-4 h-[600px] overflow-y-auto font-mono text-sm bg-stone-900 dark:bg-black"
          >
            {events.length > 0 ? (
              events.map((event) => (
                <div key={event.id} className={`py-0.5 ${getEventColor(event)}`}>
                  <span className="text-stone-500 mr-2">
                    {new Date(event.ts).toLocaleTimeString('zh-CN')}
                  </span>
                  {formatEvent(event)}
                  {event.event_type === 'runner_on_failed' && event.payload?.event_data?.res?.msg && (
                    <div className="ml-6 text-red-400 text-xs mt-1 whitespace-pre-wrap">
                      {event.payload.event_data.res.msg}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <p className="text-stone-500">等待日志输出...</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
