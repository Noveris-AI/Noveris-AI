/**
 * Gateway Upstreams Page
 *
 * Lists and manages upstream provider configurations.
 */

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { gatewayClient } from '../api/gatewayClient'
import type { Upstream, UpstreamType } from '../api/gatewayTypes'
import { UpstreamCard } from '../components/UpstreamCard'
import { UpstreamTypeBadge, HealthStatusBadge } from '../components/StatusBadge'

// Upstream type options
const typeOptions: Array<{ value: UpstreamType | ''; label: string }> = [
  { value: '', label: '全部类型' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'openai_compatible', label: 'OpenAI 兼容' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'cohere', label: 'Cohere' },
  { value: 'stable_diffusion', label: 'Stable Diffusion' },
  { value: 'custom_http', label: '自定义 HTTP' },
]

export default function UpstreamsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // State
  const [page, setPage] = useState(1)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedType, setSelectedType] = useState<UpstreamType | ''>('')
  const [typeDropdownOpen, setTypeDropdownOpen] = useState(false)

  const typeDropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (typeDropdownRef.current && !typeDropdownRef.current.contains(event.target as Node)) {
        setTypeDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Fetch upstreams
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['gateway-upstreams', page, searchQuery, selectedType],
    queryFn: () =>
      gatewayClient.listUpstreams({
        page,
        page_size: 12,
        search: searchQuery || undefined,
        type: selectedType || undefined,
      }),
  })

  // Test upstream mutation
  const testMutation = useMutation({
    mutationFn: (id: string) => gatewayClient.testUpstream(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gateway-upstreams'] })
    },
  })

  // Delete upstream mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayClient.deleteUpstream(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gateway-upstreams'] })
    },
  })

  const handleSearch = () => {
    setPage(1)
    refetch()
  }

  const handleDelete = (id: string) => {
    const upstream = data?.items.find(u => u.id === id)
    if (upstream && window.confirm(`确定要删除上游服务 "${upstream.name}" 吗？`)) {
      deleteMutation.mutate(id)
    }
  }

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Calculate stats
  const stats = data ? {
    total: data.total,
    healthy: data.items.filter(u => u.health_status === 'healthy').length,
    unhealthy: data.items.filter(u => u.health_status === 'unhealthy').length,
    enabled: data.items.filter(u => u.enabled).length,
  } : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            上游服务
          </h1>
          <p className="text-stone-600 dark:text-stone-400 mt-1">
            配置和管理 AI 模型提供商连接
          </p>
        </div>
        <button
          onClick={() => {
            // TODO: Open create modal
          }}
          className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          添加上游
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
              {stats.total}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">上游总数</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.healthy}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">健康</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {stats.unhealthy}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">异常</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-teal-600 dark:text-teal-400">
              {stats.enabled}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">已启用</div>
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
            placeholder="搜索上游名称、地址..."
            className="flex-1 px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
          />
          <button
            onClick={handleSearch}
            disabled={isLoading}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed"
          >
            搜索
          </button>
        </div>

        {/* Type Filter */}
        <div ref={typeDropdownRef} className="relative">
          <button
            onClick={() => setTypeDropdownOpen(!typeDropdownOpen)}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center gap-2"
          >
            类型
            {selectedType && (
              <UpstreamTypeBadge type={selectedType} />
            )}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {typeDropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10">
              {typeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => {
                    setSelectedType(option.value as UpstreamType | '')
                    setTypeDropdownOpen(false)
                    setPage(1)
                  }}
                  className={`w-full px-4 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors ${
                    selectedType === option.value ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-700 dark:text-stone-300'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Clear Filters */}
        {(selectedType || searchQuery) && (
          <button
            onClick={() => {
              setSelectedType('')
              setSearchQuery('')
              setPage(1)
            }}
            className="px-3 py-2 text-sm text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 transition-colors"
          >
            清除筛选
          </button>
        )}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600 mx-auto"></div>
            <p className="mt-2 text-stone-600 dark:text-stone-400">加载中...</p>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 rounded-xl border border-red-200 dark:border-red-800 p-4">
          <p className="text-sm text-red-600 dark:text-red-400">
            加载上游服务失败，请稍后重试
          </p>
        </div>
      )}

      {/* Upstreams Grid */}
      {data && data.items.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.items.map((upstream) => (
              <UpstreamCard
                key={upstream.id}
                upstream={upstream}
                onSelect={(id) => {
                  // TODO: Open detail/edit modal
                }}
                onTest={(id) => testMutation.mutate(id)}
                onDelete={handleDelete}
                isTestPending={testMutation.isPending}
              />
            ))}
          </div>

          {/* Pagination */}
          {data.total > data.page_size && (
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-stone-600 dark:text-stone-400">
                共 {data.total} 个上游，第 {data.page} / {Math.ceil(data.total / data.page_size)} 页
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page <= 1 || isLoading}
                  className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  上一页
                </button>
                <button
                  onClick={() => handlePageChange(page + 1)}
                  disabled={page >= Math.ceil(data.total / data.page_size) || isLoading}
                  className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Empty state */}
      {data && data.items.length === 0 && (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <svg className="w-16 h-16 text-stone-300 dark:text-stone-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
            </svg>
            <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">暂无上游服务</h3>
            <p className="text-stone-600 dark:text-stone-400 mb-4">
              {searchQuery || selectedType
                ? '没有找到匹配的上游服务，请调整筛选条件'
                : '开始添加您的第一个 AI 提供商'}
            </p>
            {!searchQuery && !selectedType && (
              <button
                onClick={() => {
                  // TODO: Open create modal
                }}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors"
              >
                添加上游
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
