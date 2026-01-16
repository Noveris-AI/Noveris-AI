/**
 * Job List Page
 */

import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { nodeManagementClient } from '../../nodes/api/nodeManagementClient'
import type { JobRun, JobStatus, JobTemplate } from '../../nodes/api/nodeManagementTypes'
import { JobStatusBadge } from '../../nodes/components/StatusBadge'

export function JobListPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // State
  const [jobs, setJobs] = useState<JobRun[]>([])
  const [templates, setTemplates] = useState<JobTemplate[]>([])
  const [total, setTotal] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)

  // Filters
  const [selectedStatus, setSelectedStatus] = useState<JobStatus | ''>('')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const nodeIdFromUrl = searchParams.get('node_id')

  // Dropdowns
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false)
  const [templateDropdownOpen, setTemplateDropdownOpen] = useState(false)

  const statusDropdownRef = useRef<HTMLDivElement>(null)
  const templateDropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (statusDropdownRef.current && !statusDropdownRef.current.contains(event.target as Node)) {
        setStatusDropdownOpen(false)
      }
      if (templateDropdownRef.current && !templateDropdownRef.current.contains(event.target as Node)) {
        setTemplateDropdownOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Fetch jobs
  const fetchJobs = async (page: number = currentPage) => {
    setLoading(true)
    try {
      const response = await nodeManagementClient.listJobRuns({
        page,
        page_size: 20,
        status: selectedStatus || undefined,
        template_id: selectedTemplateId || undefined,
        node_id: nodeIdFromUrl || undefined,
      })

      setJobs(response.runs)
      setTotal(response.pagination.total)
      setTotalPages(response.pagination.total_pages)
      setCurrentPage(response.pagination.page)
    } catch (error) {
      console.error('Failed to fetch jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  // Fetch templates
  const fetchTemplates = async () => {
    try {
      const response = await nodeManagementClient.listJobTemplates(undefined, false)
      setTemplates(response.templates)
    } catch (error) {
      console.error('Failed to fetch templates:', error)
    }
  }

  // Initial load
  useEffect(() => {
    fetchJobs()
    fetchTemplates()
  }, [])

  // Refetch when filters change
  useEffect(() => {
    fetchJobs(1)
  }, [selectedStatus, selectedTemplateId, nodeIdFromUrl])

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

  // Status options
  const statusOptions: Array<{ value: JobStatus | ''; label: string }> = [
    { value: '', label: '全部状态' },
    { value: 'RUNNING', label: '运行中' },
    { value: 'PENDING', label: '等待中' },
    { value: 'SUCCEEDED', label: '成功' },
    { value: 'FAILED', label: '失败' },
    { value: 'CANCELED', label: '已取消' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            任务中心
          </h1>
          <p className="text-stone-600 dark:text-stone-400 mt-1">
            查看和管理 Ansible 任务执行记录
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Status Filter */}
        <div ref={statusDropdownRef} className="relative">
          <button
            onClick={() => setStatusDropdownOpen(!statusDropdownOpen)}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center gap-2"
          >
            状态
            {selectedStatus && (
              <JobStatusBadge status={selectedStatus} size="sm" />
            )}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {statusDropdownOpen && (
            <div className="absolute left-0 mt-2 w-48 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10">
              {statusOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => {
                    setSelectedStatus(option.value as JobStatus | '')
                    setStatusDropdownOpen(false)
                  }}
                  className={`w-full px-4 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors ${
                    selectedStatus === option.value ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-700 dark:text-stone-300'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Template Filter */}
        <div ref={templateDropdownRef} className="relative">
          <button
            onClick={() => setTemplateDropdownOpen(!templateDropdownOpen)}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center gap-2"
          >
            模板
            {selectedTemplateId && (
              <span className="px-2 py-0.5 text-xs bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded-full">
                1
              </span>
            )}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {templateDropdownOpen && (
            <div className="absolute left-0 mt-2 w-64 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10 max-h-64 overflow-y-auto">
              <button
                onClick={() => {
                  setSelectedTemplateId('')
                  setTemplateDropdownOpen(false)
                }}
                className={`w-full px-4 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors ${
                  !selectedTemplateId ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-700 dark:text-stone-300'
                }`}
              >
                全部模板
              </button>
              {templates.map((template) => (
                <button
                  key={template.id}
                  onClick={() => {
                    setSelectedTemplateId(template.id)
                    setTemplateDropdownOpen(false)
                  }}
                  className={`w-full px-4 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors ${
                    selectedTemplateId === template.id ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-700 dark:text-stone-300'
                  }`}
                >
                  {template.display_name || template.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {nodeIdFromUrl && (
          <span className="px-3 py-1.5 bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-300 rounded-lg text-sm flex items-center gap-2">
            已筛选节点
            <button
              onClick={() => navigate('/dashboard/jobs')}
              className="text-stone-400 hover:text-stone-600 dark:hover:text-stone-200"
            >
              ×
            </button>
          </span>
        )}

        {/* Clear Filters */}
        {(selectedStatus || selectedTemplateId) && (
          <button
            onClick={() => {
              setSelectedStatus('')
              setSelectedTemplateId('')
            }}
            className="px-3 py-2 text-sm text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 transition-colors"
          >
            清除筛选
          </button>
        )}

        {/* Refresh */}
        <button
          onClick={() => fetchJobs(currentPage)}
          disabled={loading}
          className="px-3 py-2 text-sm text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 transition-colors disabled:opacity-50"
        >
          <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>

      {/* Job Table */}
      <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 overflow-hidden">
        <table className="w-full">
          <thead className="bg-stone-50 dark:bg-stone-700/50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                任务
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                状态
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                节点数
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                耗时
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                创建时间
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                执行人
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-200 dark:divide-stone-700">
            {loading && jobs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-teal-600 mx-auto"></div>
                  <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">加载中...</p>
                </td>
              </tr>
            ) : jobs.length > 0 ? (
              jobs.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => navigate(`/dashboard/jobs/${job.id}`)}
                  className="hover:bg-stone-50 dark:hover:bg-stone-700/50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-4">
                    <div>
                      <p className="font-medium text-stone-900 dark:text-stone-100">
                        {job.template_name || '未知模板'}
                      </p>
                      <p className="text-xs text-stone-500 dark:text-stone-400 font-mono">
                        {job.id.slice(0, 8)}...
                      </p>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <JobStatusBadge status={job.status} size="sm" />
                  </td>
                  <td className="px-4 py-4 text-sm text-stone-600 dark:text-stone-400">
                    {job.node_count}
                  </td>
                  <td className="px-4 py-4 text-sm text-stone-600 dark:text-stone-400">
                    {formatDuration(job.duration_seconds)}
                  </td>
                  <td className="px-4 py-4 text-sm text-stone-600 dark:text-stone-400">
                    {formatDate(job.created_at)}
                  </td>
                  <td className="px-4 py-4 text-sm text-stone-600 dark:text-stone-400">
                    {job.created_by_email || '-'}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center">
                  <svg className="w-12 h-12 text-stone-300 dark:text-stone-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  <p className="text-stone-500 dark:text-stone-400">暂无任务记录</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-stone-600 dark:text-stone-400">
            共 {total} 条记录，第 {currentPage} / {totalPages} 页
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchJobs(currentPage - 1)}
              disabled={currentPage <= 1 || loading}
              className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              上一页
            </button>
            <button
              onClick={() => fetchJobs(currentPage + 1)}
              disabled={currentPage >= totalPages || loading}
              className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              下一页
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
