/**
 * Deployment List Page
 */

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { deploymentClient } from '../api/deploymentClient'
import type {
  Deployment,
  DeploymentStatus,
  DeploymentFramework,
  DeploymentStats,
} from '../api/deploymentTypes'
import { DeploymentCard } from '../components/DeploymentCard'
import { DeploymentStatusBadge } from '../components/StatusBadge'

export function DeploymentListPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  // State
  const [deployments, setDeployments] = useState<Deployment[]>([])
  const [total, setTotal] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [initialLoading, setInitialLoading] = useState(true)

  // Stats
  const [stats, setStats] = useState<DeploymentStats | null>(null)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedStatus, setSelectedStatus] = useState<DeploymentStatus | ''>('')
  const [selectedFramework, setSelectedFramework] = useState<DeploymentFramework | ''>('')

  // Dropdowns
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false)
  const [frameworkDropdownOpen, setFrameworkDropdownOpen] = useState(false)

  const statusDropdownRef = useRef<HTMLDivElement>(null)
  const frameworkDropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (statusDropdownRef.current && !statusDropdownRef.current.contains(event.target as Node)) {
        setStatusDropdownOpen(false)
      }
      if (frameworkDropdownRef.current && !frameworkDropdownRef.current.contains(event.target as Node)) {
        setFrameworkDropdownOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Fetch deployments
  const fetchDeployments = async (page: number = currentPage) => {
    setLoading(true)
    try {
      const response = await deploymentClient.listDeployments({
        page,
        page_size: 12,
        search: searchQuery || undefined,
        status: selectedStatus || undefined,
        framework: selectedFramework || undefined,
      })

      setDeployments(response.deployments)
      setTotal(response.pagination.total)
      setTotalPages(response.pagination.total_pages)
      setCurrentPage(response.pagination.page)

      // Calculate stats from response
      const statusCounts: Record<string, number> = {}
      const frameworkCounts: Record<string, number> = {}
      let running = 0
      let failed = 0

      response.deployments.forEach(d => {
        statusCounts[d.status] = (statusCounts[d.status] || 0) + 1
        frameworkCounts[d.framework] = (frameworkCounts[d.framework] || 0) + 1
        if (d.status === 'RUNNING') running++
        if (d.status === 'FAILED') failed++
      })

      setStats({
        total: response.pagination.total,
        by_status: statusCounts,
        by_framework: frameworkCounts,
        running,
        failed,
      })
    } catch (error) {
      console.error('Failed to fetch deployments:', error)
    } finally {
      setLoading(false)
      setInitialLoading(false)
    }
  }

  // Initial load
  useEffect(() => {
    fetchDeployments()
  }, [])

  // Refetch when filters change
  useEffect(() => {
    fetchDeployments(1)
  }, [selectedStatus, selectedFramework])

  // Handle search
  const handleSearch = () => {
    fetchDeployments(1)
  }

  // Handle page change
  const handlePageChange = (page: number) => {
    fetchDeployments(page)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Handle deployment actions
  const handleStart = async (id: string) => {
    try {
      await deploymentClient.startDeployment(id)
      fetchDeployments(currentPage)
    } catch (error) {
      console.error('Failed to start deployment:', error)
    }
  }

  const handleStop = async (id: string) => {
    try {
      await deploymentClient.stopDeployment(id)
      fetchDeployments(currentPage)
    } catch (error) {
      console.error('Failed to stop deployment:', error)
    }
  }

  // Status options
  const statusOptions: Array<{ value: DeploymentStatus | ''; label: string }> = [
    { value: '', label: '全部状态' },
    { value: 'RUNNING', label: '运行中' },
    { value: 'STOPPED', label: '已停止' },
    { value: 'PENDING', label: '等待中' },
    { value: 'STARTING', label: '启动中' },
    { value: 'FAILED', label: '失败' },
    { value: 'DOWNLOADING', label: '下载中' },
    { value: 'INSTALLING', label: '安装中' },
  ]

  // Framework options
  const frameworkOptions: Array<{ value: DeploymentFramework | ''; label: string }> = [
    { value: '', label: '全部框架' },
    { value: 'vllm', label: 'vLLM' },
    { value: 'sglang', label: 'SGLang' },
    { value: 'xinference', label: 'Xinference' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            {t('deployment.title', '模型部署')}
          </h1>
          <p className="text-stone-600 dark:text-stone-400 mt-1">
            部署和管理大语言模型推理服务
          </p>
        </div>
        <button
          onClick={() => navigate('/dashboard/deployment/create')}
          className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          新建部署
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
          <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            {stats?.total || 0}
          </div>
          <div className="text-sm text-stone-500 dark:text-stone-400">部署总数</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">
            {stats?.running || 0}
          </div>
          <div className="text-sm text-stone-500 dark:text-stone-400">运行中</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
          <div className="text-2xl font-bold text-red-600 dark:text-red-400">
            {stats?.failed || 0}
          </div>
          <div className="text-sm text-stone-500 dark:text-stone-400">失败</div>
        </div>
        <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
          <div className="flex items-center gap-2 text-sm text-stone-600 dark:text-stone-400">
            {stats?.by_framework && Object.entries(stats.by_framework).map(([fw, count]) => (
              <span key={fw} className="px-2 py-0.5 bg-stone-100 dark:bg-stone-700 rounded">
                {fw}: {count}
              </span>
            ))}
          </div>
          <div className="text-sm text-stone-500 dark:text-stone-400 mt-1">按框架</div>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search Bar */}
        <div className="flex-1 min-w-[200px] flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="搜索部署名称、模型..."
            className="flex-1 px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed"
          >
            搜索
          </button>
        </div>

        {/* Status Filter */}
        <div ref={statusDropdownRef} className="relative">
          <button
            onClick={() => setStatusDropdownOpen(!statusDropdownOpen)}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center gap-2"
          >
            状态
            {selectedStatus && (
              <DeploymentStatusBadge status={selectedStatus} size="sm" />
            )}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {statusDropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10">
              {statusOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => {
                    setSelectedStatus(option.value as DeploymentStatus | '')
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

        {/* Framework Filter */}
        <div ref={frameworkDropdownRef} className="relative">
          <button
            onClick={() => setFrameworkDropdownOpen(!frameworkDropdownOpen)}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center gap-2"
          >
            框架
            {selectedFramework && (
              <span className="px-2 py-0.5 text-xs bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded-full">
                {selectedFramework}
              </span>
            )}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {frameworkDropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10">
              {frameworkOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => {
                    setSelectedFramework(option.value as DeploymentFramework | '')
                    setFrameworkDropdownOpen(false)
                  }}
                  className={`w-full px-4 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors ${
                    selectedFramework === option.value ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-700 dark:text-stone-300'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Clear Filters */}
        {(selectedStatus || selectedFramework || searchQuery) && (
          <button
            onClick={() => {
              setSelectedStatus('')
              setSelectedFramework('')
              setSearchQuery('')
              fetchDeployments(1)
            }}
            className="px-3 py-2 text-sm text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 transition-colors"
          >
            清除筛选
          </button>
        )}
      </div>

      {/* Deployment Grid */}
      {initialLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600 mx-auto"></div>
            <p className="mt-2 text-stone-600 dark:text-stone-400">加载中...</p>
          </div>
        </div>
      ) : deployments.length > 0 ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {deployments.map((deployment) => (
              <DeploymentCard
                key={deployment.id}
                deployment={deployment}
                onSelect={(id) => navigate(`/dashboard/deployment/${id}`)}
                onStart={handleStart}
                onStop={handleStop}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-stone-600 dark:text-stone-400">
                共 {total} 个部署，第 {currentPage} / {totalPages} 页
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage <= 1 || loading}
                  className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  上一页
                </button>
                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage >= totalPages || loading}
                  className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <svg className="w-16 h-16 text-stone-300 dark:text-stone-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
            <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">暂无部署</h3>
            <p className="text-stone-600 dark:text-stone-400 mb-4">
              {searchQuery || selectedStatus || selectedFramework
                ? '没有找到匹配的部署，请调整筛选条件'
                : '开始创建您的第一个模型部署'}
            </p>
            {!searchQuery && !selectedStatus && !selectedFramework && (
              <button
                onClick={() => navigate('/dashboard/deployment/create')}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors"
              >
                新建部署
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
