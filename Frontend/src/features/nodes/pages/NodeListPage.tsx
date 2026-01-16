/**
 * Node List Page
 */

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { nodeManagementClient } from '../api/nodeManagementClient'
import type {
  Node as NodeType,
  NodeStatus,
  AcceleratorType,
  NodeGroup,
  DashboardStats,
} from '../api/nodeManagementTypes'
import { NodeCard } from '../components/NodeCard'
import { NodeStatusBadge } from '../components/StatusBadge'

export function NodeListPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  // State
  const [nodes, setNodes] = useState<NodeType[]>([])
  const [groups, setGroups] = useState<NodeGroup[]>([])
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [total, setTotal] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [hasNext, setHasNext] = useState(false)
  const [hasPrev, setHasPrev] = useState(false)
  const [loading, setLoading] = useState(true)
  const [initialLoading, setInitialLoading] = useState(true)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedStatus, setSelectedStatus] = useState<NodeStatus | ''>('')
  const [selectedAccelType, setSelectedAccelType] = useState<AcceleratorType | ''>('')
  const [selectedGroupId, setSelectedGroupId] = useState<string>('')

  // Dropdowns
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false)
  const [accelDropdownOpen, setAccelDropdownOpen] = useState(false)
  const [groupDropdownOpen, setGroupDropdownOpen] = useState(false)

  const statusDropdownRef = useRef<HTMLDivElement>(null)
  const accelDropdownRef = useRef<HTMLDivElement>(null)
  const groupDropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (statusDropdownRef.current && !statusDropdownRef.current.contains(event.target as Node)) {
        setStatusDropdownOpen(false)
      }
      if (accelDropdownRef.current && !accelDropdownRef.current.contains(event.target as Node)) {
        setAccelDropdownOpen(false)
      }
      if (groupDropdownRef.current && !groupDropdownRef.current.contains(event.target as Node)) {
        setGroupDropdownOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Fetch nodes
  const fetchNodes = async (page: number = currentPage) => {
    setLoading(true)
    try {
      const response = await nodeManagementClient.listNodes({
        page,
        page_size: 12,
        search: searchQuery || undefined,
        status: selectedStatus || undefined,
        accel_type: selectedAccelType || undefined,
        group_id: selectedGroupId || undefined,
      })

      setNodes(response.nodes)
      setTotal(response.pagination.total)
      setTotalPages(response.pagination.total_pages)
      setCurrentPage(response.pagination.page)
      setHasNext(response.pagination.has_next)
      setHasPrev(response.pagination.has_prev)
    } catch (error) {
      console.error('Failed to fetch nodes:', error)
    } finally {
      setLoading(false)
      setInitialLoading(false)
    }
  }

  // Fetch initial data
  const fetchInitialData = async () => {
    try {
      const [groupsResponse, statsResponse] = await Promise.all([
        nodeManagementClient.listNodeGroups(1, 100),
        nodeManagementClient.getDashboardStats(),
      ])
      setGroups(groupsResponse.groups)
      setStats(statsResponse)
    } catch (error) {
      console.error('Failed to fetch initial data:', error)
    }
  }

  // Initial load
  useEffect(() => {
    fetchNodes()
    fetchInitialData()
  }, [])

  // Refetch when filters change
  useEffect(() => {
    fetchNodes(1)
  }, [selectedStatus, selectedAccelType, selectedGroupId])

  // Handle search
  const handleSearch = () => {
    fetchNodes(1)
  }

  // Handle page change
  const handlePageChange = (page: number) => {
    fetchNodes(page)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Status options
  const statusOptions: Array<{ value: NodeStatus | ''; label: string }> = [
    { value: '', label: '全部状态' },
    { value: 'READY', label: '就绪' },
    { value: 'NEW', label: '新建' },
    { value: 'UNREACHABLE', label: '不可达' },
    { value: 'MAINTENANCE', label: '维护中' },
    { value: 'DECOMMISSIONED', label: '已下线' },
  ]

  // Accelerator options
  const accelOptions: Array<{ value: AcceleratorType | ''; label: string }> = [
    { value: '', label: '全部类型' },
    { value: 'nvidia_gpu', label: 'NVIDIA GPU' },
    { value: 'amd_gpu', label: 'AMD GPU' },
    { value: 'intel_gpu', label: 'Intel GPU' },
    { value: 'ascend_npu', label: 'Ascend NPU' },
    { value: 't_head_npu', label: 'T-Head NPU' },
    { value: 'generic_accel', label: 'Generic Accelerator' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            {t('nodes.title', '节点管理')}
          </h1>
          <p className="text-stone-600 dark:text-stone-400 mt-1">
            管理和监控集群中的计算节点
          </p>
        </div>
        <button
          onClick={() => navigate('/dashboard/nodes/add')}
          className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          添加节点
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
              {stats.nodes.total}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">总节点数</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.nodes.by_status?.READY || 0}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">就绪节点</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {stats.nodes.unreachable}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">不可达</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-teal-600 dark:text-teal-400">
              {stats.total_accelerators}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">加速器总数</div>
          </div>
        </div>
      )}

      {/* Filters Bar */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search Bar */}
        <div className="flex-1 min-w-[200px] flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="搜索节点名称、主机地址..."
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
              <NodeStatusBadge status={selectedStatus} size="sm" />
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
                    setSelectedStatus(option.value as NodeStatus | '')
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

        {/* Accelerator Type Filter */}
        <div ref={accelDropdownRef} className="relative">
          <button
            onClick={() => setAccelDropdownOpen(!accelDropdownOpen)}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center gap-2"
          >
            加速器
            {selectedAccelType && (
              <span className="px-2 py-0.5 text-xs bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded-full">
                1
              </span>
            )}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {accelDropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10">
              {accelOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => {
                    setSelectedAccelType(option.value as AcceleratorType | '')
                    setAccelDropdownOpen(false)
                  }}
                  className={`w-full px-4 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors ${
                    selectedAccelType === option.value ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-700 dark:text-stone-300'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Group Filter */}
        <div ref={groupDropdownRef} className="relative">
          <button
            onClick={() => setGroupDropdownOpen(!groupDropdownOpen)}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center gap-2"
          >
            分组
            {selectedGroupId && (
              <span className="px-2 py-0.5 text-xs bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded-full">
                1
              </span>
            )}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {groupDropdownOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10 max-h-64 overflow-y-auto">
              <button
                onClick={() => {
                  setSelectedGroupId('')
                  setGroupDropdownOpen(false)
                }}
                className={`w-full px-4 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors ${
                  !selectedGroupId ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-700 dark:text-stone-300'
                }`}
              >
                全部分组
              </button>
              {groups.map((group) => (
                <button
                  key={group.id}
                  onClick={() => {
                    setSelectedGroupId(group.id)
                    setGroupDropdownOpen(false)
                  }}
                  className={`w-full px-4 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors flex items-center justify-between ${
                    selectedGroupId === group.id ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-700 dark:text-stone-300'
                  }`}
                >
                  <span>{group.display_name || group.name}</span>
                  <span className="text-xs text-stone-400">({group.node_count})</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Clear Filters */}
        {(selectedStatus || selectedAccelType || selectedGroupId || searchQuery) && (
          <button
            onClick={() => {
              setSelectedStatus('')
              setSelectedAccelType('')
              setSelectedGroupId('')
              setSearchQuery('')
              fetchNodes(1)
            }}
            className="px-3 py-2 text-sm text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 transition-colors"
          >
            清除筛选
          </button>
        )}
      </div>

      {/* Node Grid */}
      {initialLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600 mx-auto"></div>
            <p className="mt-2 text-stone-600 dark:text-stone-400">加载中...</p>
          </div>
        </div>
      ) : nodes.length > 0 ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
            {nodes.map((node) => (
              <NodeCard
                key={node.id}
                node={node}
                onSelect={(id) => navigate(`/dashboard/nodes/${id}`)}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-stone-600 dark:text-stone-400">
                共 {total} 个节点，第 {currentPage} / {totalPages} 页
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={!hasPrev || loading}
                  className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  上一页
                </button>
                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={!hasNext || loading}
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
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
            </svg>
            <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">暂无节点</h3>
            <p className="text-stone-600 dark:text-stone-400 mb-4">
              {searchQuery || selectedStatus || selectedAccelType || selectedGroupId
                ? '没有找到匹配的节点，请调整筛选条件'
                : '开始添加您的第一个计算节点'}
            </p>
            {!searchQuery && !selectedStatus && !selectedAccelType && !selectedGroupId && (
              <button
                onClick={() => navigate('/dashboard/nodes/add')}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors"
              >
                添加节点
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
