/**
 * Node Detail Page
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { nodeManagementClient } from '../api/nodeManagementClient'
import type { NodeDetail, JobRun, JobTemplate } from '../api/nodeManagementTypes'
import { NodeStatusBadge, JobStatusBadge } from '../components/StatusBadge'
import { AcceleratorSummary, AcceleratorIcon } from '../components/AcceleratorIcon'

type TabType = 'overview' | 'hardware' | 'jobs' | 'facts'

export function NodeDetailPage() {
  const { t } = useTranslation()
  const { nodeId } = useParams<{ nodeId: string }>()
  const navigate = useNavigate()

  // State
  const [node, setNode] = useState<NodeDetail | null>(null)
  const [recentJobs, setRecentJobs] = useState<JobRun[]>([])
  const [templates, setTemplates] = useState<JobTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('overview')

  // Action states
  const [collectingFacts, setCollectingFacts] = useState(false)
  const [runningJob, setRunningJob] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<string>('')
  const [showRunJobModal, setShowRunJobModal] = useState(false)

  // Fetch node details
  const fetchNode = async () => {
    if (!nodeId) return

    setLoading(true)
    setError(null)

    try {
      const [nodeData, jobsData, templatesData] = await Promise.all([
        nodeManagementClient.getNode(nodeId),
        nodeManagementClient.listJobRuns({ node_id: nodeId, page_size: 5 }),
        nodeManagementClient.listJobTemplates(),
      ])

      setNode(nodeData)
      setRecentJobs(jobsData.runs)
      setTemplates(templatesData.templates)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchNode()
  }, [nodeId])

  // Handle collect facts
  const handleCollectFacts = async () => {
    if (!nodeId) return

    setCollectingFacts(true)
    try {
      const jobRun = await nodeManagementClient.collectNodeFacts(nodeId)
      // Navigate to job detail or show success message
      navigate(`/dashboard/jobs/${jobRun.id}`)
    } catch (err) {
      console.error('Failed to collect facts:', err)
    } finally {
      setCollectingFacts(false)
    }
  }

  // Handle run job
  const handleRunJob = async () => {
    if (!nodeId || !selectedTemplate) return

    setRunningJob(true)
    try {
      const jobRun = await nodeManagementClient.runJobOnNode(nodeId, {
        template_id: selectedTemplate,
        target_type: 'node',
        target_node_ids: [nodeId],
      })
      setShowRunJobModal(false)
      navigate(`/dashboard/jobs/${jobRun.id}`)
    } catch (err) {
      console.error('Failed to run job:', err)
    } finally {
      setRunningJob(false)
    }
  }

  // Format helpers
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleString('zh-CN')
  }

  const formatMemory = (mb?: number) => {
    if (!mb) return '-'
    if (mb >= 1024 * 1024) return `${(mb / 1024 / 1024).toFixed(1)} TB`
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
    return `${mb} MB`
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

  if (error || !node) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <svg className="w-16 h-16 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">
            {error || '节点不存在'}
          </h3>
          <button
            onClick={() => navigate('/dashboard/nodes')}
            className="text-teal-600 hover:text-teal-700 dark:text-teal-400"
          >
            返回节点列表
          </button>
        </div>
      </div>
    )
  }

  const tabs: Array<{ key: TabType; label: string }> = [
    { key: 'overview', label: '概览' },
    { key: 'hardware', label: '硬件' },
    { key: 'jobs', label: '任务' },
    { key: 'facts', label: 'Facts' },
  ]

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/dashboard/nodes" className="hover:text-teal-600 dark:hover:text-teal-400">
          节点管理
        </Link>
        <span>/</span>
        <span className="text-stone-900 dark:text-stone-100">{node.display_name || node.name}</span>
      </nav>

      {/* Header */}
      <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
                {node.display_name || node.name}
              </h1>
              <NodeStatusBadge status={node.status} />
            </div>
            <p className="text-stone-600 dark:text-stone-400">
              {node.host}:{node.port} · {node.connection_type === 'local' ? '本地连接' : `SSH (${node.ssh_user})`}
            </p>
            {node.os_release && (
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
                {node.os_release} · {node.kernel_version} · {node.architecture}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCollectFacts}
              disabled={collectingFacts}
              className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {collectingFacts ? (
                <div className="w-4 h-4 border-2 border-stone-400 border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              )}
              收集 Facts
            </button>
            <button
              onClick={() => setShowRunJobModal(true)}
              className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              执行任务
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-stone-200 dark:border-stone-700">
        <nav className="flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-teal-600 text-teal-600 dark:text-teal-400'
                  : 'border-transparent text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* System Info */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">系统信息</h3>
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">CPU</dt>
                <dd className="text-stone-900 dark:text-stone-100">
                  {node.cpu_cores ? `${node.cpu_cores} 核` : '-'}
                  {node.cpu_model && <span className="text-sm text-stone-500 ml-2">({node.cpu_model})</span>}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">内存</dt>
                <dd className="text-stone-900 dark:text-stone-100">{formatMemory(node.mem_mb)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">磁盘</dt>
                <dd className="text-stone-900 dark:text-stone-100">{formatMemory(node.disk_mb)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">架构</dt>
                <dd className="text-stone-900 dark:text-stone-100">{node.architecture || '-'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">内核</dt>
                <dd className="text-stone-900 dark:text-stone-100">{node.kernel_version || '-'}</dd>
              </div>
            </dl>
          </div>

          {/* Accelerators Summary */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">加速器</h3>
            {node.accelerators.length > 0 ? (
              <div className="space-y-3">
                {node.accelerators.slice(0, 4).map((acc) => (
                  <div key={acc.id} className="flex items-center justify-between p-3 bg-stone-50 dark:bg-stone-700/50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <AcceleratorIcon type={acc.type} size="md" />
                      <div>
                        <p className="font-medium text-stone-900 dark:text-stone-100">{acc.model}</p>
                        <p className="text-sm text-stone-500 dark:text-stone-400">
                          {acc.vendor} · {formatMemory(acc.memory_mb)}
                        </p>
                      </div>
                    </div>
                    {acc.utilization_percent !== undefined && (
                      <div className="text-right">
                        <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                          {acc.utilization_percent}%
                        </p>
                        <p className="text-xs text-stone-400">利用率</p>
                      </div>
                    )}
                  </div>
                ))}
                {node.accelerators.length > 4 && (
                  <p className="text-sm text-stone-500 text-center">
                    还有 {node.accelerators.length - 4} 个加速器
                  </p>
                )}
              </div>
            ) : (
              <p className="text-stone-500 dark:text-stone-400 text-center py-4">暂无加速器</p>
            )}
          </div>

          {/* Groups */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">所属分组</h3>
            {node.group_names.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {node.group_names.map((groupName) => (
                  <span
                    key={groupName}
                    className="px-3 py-1.5 bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 rounded-lg text-sm"
                  >
                    {groupName}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-stone-500 dark:text-stone-400">未分配分组</p>
            )}
          </div>

          {/* Connection Info */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">连接信息</h3>
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">连接类型</dt>
                <dd className="text-stone-900 dark:text-stone-100">
                  {node.connection_type === 'local' ? '本地' : 'SSH'}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">凭据状态</dt>
                <dd className="text-stone-900 dark:text-stone-100">
                  {node.credentials_exist ? (
                    <span className="text-green-600 dark:text-green-400">已配置</span>
                  ) : (
                    <span className="text-amber-600 dark:text-amber-400">未配置</span>
                  )}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">BMC/IPMI</dt>
                <dd className="text-stone-900 dark:text-stone-100">
                  {node.bmc_configured ? (
                    <span className="text-green-600 dark:text-green-400">已配置</span>
                  ) : (
                    <span className="text-stone-400">未配置</span>
                  )}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-stone-500 dark:text-stone-400">最后在线</dt>
                <dd className="text-stone-900 dark:text-stone-100">{formatDate(node.last_seen_at)}</dd>
              </div>
            </dl>
          </div>
        </div>
      )}

      {activeTab === 'hardware' && (
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700">
          <div className="p-6 border-b border-stone-200 dark:border-stone-700">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100">加速器详情</h3>
          </div>
          {node.accelerators.length > 0 ? (
            <div className="divide-y divide-stone-200 dark:divide-stone-700">
              {node.accelerators.map((acc) => (
                <div key={acc.id} className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <AcceleratorIcon type={acc.type} size="lg" />
                      <div>
                        <h4 className="font-semibold text-stone-900 dark:text-stone-100">{acc.model}</h4>
                        <p className="text-sm text-stone-500 dark:text-stone-400">
                          {acc.vendor} · 设备 {acc.device_id}
                        </p>
                      </div>
                    </div>
                    {acc.health_status && (
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        acc.health_status === 'healthy'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                      }`}>
                        {acc.health_status === 'healthy' ? '健康' : acc.health_status}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <dt className="text-stone-500 dark:text-stone-400">显存</dt>
                      <dd className="font-medium text-stone-900 dark:text-stone-100">
                        {formatMemory(acc.memory_mb)}
                      </dd>
                    </div>
                    {acc.cores && (
                      <div>
                        <dt className="text-stone-500 dark:text-stone-400">计算单元</dt>
                        <dd className="font-medium text-stone-900 dark:text-stone-100">{acc.cores}</dd>
                      </div>
                    )}
                    {acc.driver_version && (
                      <div>
                        <dt className="text-stone-500 dark:text-stone-400">驱动版本</dt>
                        <dd className="font-medium text-stone-900 dark:text-stone-100">{acc.driver_version}</dd>
                      </div>
                    )}
                    {acc.temperature_celsius !== undefined && (
                      <div>
                        <dt className="text-stone-500 dark:text-stone-400">温度</dt>
                        <dd className="font-medium text-stone-900 dark:text-stone-100">
                          {acc.temperature_celsius}°C
                        </dd>
                      </div>
                    )}
                    {acc.power_usage_watts !== undefined && (
                      <div>
                        <dt className="text-stone-500 dark:text-stone-400">功耗</dt>
                        <dd className="font-medium text-stone-900 dark:text-stone-100">
                          {acc.power_usage_watts}W
                        </dd>
                      </div>
                    )}
                    {acc.utilization_percent !== undefined && (
                      <div>
                        <dt className="text-stone-500 dark:text-stone-400">利用率</dt>
                        <dd className="font-medium text-stone-900 dark:text-stone-100">
                          {acc.utilization_percent}%
                        </dd>
                      </div>
                    )}
                    {acc.bus_id && (
                      <div>
                        <dt className="text-stone-500 dark:text-stone-400">PCIe Bus</dt>
                        <dd className="font-medium text-stone-900 dark:text-stone-100">{acc.bus_id}</dd>
                      </div>
                    )}
                    {acc.compute_capability && (
                      <div>
                        <dt className="text-stone-500 dark:text-stone-400">计算能力</dt>
                        <dd className="font-medium text-stone-900 dark:text-stone-100">
                          {acc.compute_capability}
                        </dd>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-12 text-center">
              <svg className="w-12 h-12 text-stone-300 dark:text-stone-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
              <p className="text-stone-500 dark:text-stone-400">该节点暂无加速器</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'jobs' && (
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700">
          <div className="p-6 border-b border-stone-200 dark:border-stone-700 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100">最近任务</h3>
            <Link
              to={`/dashboard/jobs?node_id=${node.id}`}
              className="text-sm text-teal-600 hover:text-teal-700 dark:text-teal-400"
            >
              查看全部 →
            </Link>
          </div>
          {recentJobs.length > 0 ? (
            <div className="divide-y divide-stone-200 dark:divide-stone-700">
              {recentJobs.map((job) => (
                <Link
                  key={job.id}
                  to={`/dashboard/jobs/${job.id}`}
                  className="p-4 flex items-center justify-between hover:bg-stone-50 dark:hover:bg-stone-700/50 transition-colors"
                >
                  <div>
                    <p className="font-medium text-stone-900 dark:text-stone-100">
                      {job.template_name || '未知模板'}
                    </p>
                    <p className="text-sm text-stone-500 dark:text-stone-400">
                      {formatDate(job.created_at)}
                    </p>
                  </div>
                  <JobStatusBadge status={job.status} size="sm" />
                </Link>
              ))}
            </div>
          ) : (
            <div className="p-12 text-center">
              <p className="text-stone-500 dark:text-stone-400">暂无任务记录</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'facts' && (
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700">
          <div className="p-6 border-b border-stone-200 dark:border-stone-700 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100">Ansible Facts</h3>
            <button
              onClick={handleCollectFacts}
              disabled={collectingFacts}
              className="text-sm text-teal-600 hover:text-teal-700 dark:text-teal-400 disabled:opacity-50"
            >
              {collectingFacts ? '收集中...' : '重新收集'}
            </button>
          </div>
          {node.last_facts ? (
            <div className="p-6">
              <pre className="bg-stone-50 dark:bg-stone-900 rounded-lg p-4 overflow-x-auto text-sm text-stone-800 dark:text-stone-200">
                {JSON.stringify(node.last_facts, null, 2)}
              </pre>
            </div>
          ) : (
            <div className="p-12 text-center">
              <svg className="w-12 h-12 text-stone-300 dark:text-stone-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-stone-500 dark:text-stone-400 mb-4">暂无 Facts 数据</p>
              <button
                onClick={handleCollectFacts}
                disabled={collectingFacts}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-sm disabled:opacity-50"
              >
                收集 Facts
              </button>
            </div>
          )}
        </div>
      )}

      {/* Run Job Modal */}
      {showRunJobModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-stone-800 rounded-xl w-full max-w-md p-6 m-4">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">
              执行任务
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                  选择任务模板
                </label>
                <select
                  value={selectedTemplate}
                  onChange={(e) => setSelectedTemplate(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                >
                  <option value="">选择模板...</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.display_name || template.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowRunJobModal(false)}
                className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-700"
              >
                取消
              </button>
              <button
                onClick={handleRunJob}
                disabled={!selectedTemplate || runningJob}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {runningJob && (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                )}
                执行
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
