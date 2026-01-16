/**
 * Gateway Virtual Models Page
 *
 * Lists and manages virtual model configurations.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { gatewayClient } from '../api/gatewayClient'
import type { VirtualModel } from '../api/gatewayTypes'
import { VirtualModelCard } from '../components/VirtualModelCard'

export default function VirtualModelsPage() {
  const queryClient = useQueryClient()

  // State
  const [page, setPage] = useState(1)
  const [searchQuery, setSearchQuery] = useState('')

  // Fetch virtual models
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['gateway-virtual-models', page, searchQuery],
    queryFn: () =>
      gatewayClient.listVirtualModels({
        page,
        page_size: 12,
        search: searchQuery || undefined,
      }),
  })

  // Delete virtual model mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayClient.deleteVirtualModel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gateway-virtual-models'] })
    },
  })

  const handleSearch = () => {
    setPage(1)
    refetch()
  }

  const handleDelete = (id: string) => {
    const model = data?.items.find(m => m.id === id)
    if (model && window.confirm(`确定要删除虚拟模型 "${model.name}" 吗？`)) {
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
    enabled: data.items.filter(m => m.enabled).length,
    withRoute: data.items.filter(m => m.default_route_id).length,
  } : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            虚拟模型
          </h1>
          <p className="text-stone-600 dark:text-stone-400 mt-1">
            定义模型别名和能力映射
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
          创建模型
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
              {stats.total}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">模型总数</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.enabled}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">已启用</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-teal-600 dark:text-teal-400">
              {stats.withRoute}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">已配置路由</div>
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
            placeholder="搜索模型名称..."
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

        {/* Clear Filters */}
        {searchQuery && (
          <button
            onClick={() => {
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
            加载虚拟模型失败，请稍后重试
          </p>
        </div>
      )}

      {/* Virtual Models Grid */}
      {data && data.items.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.items.map((model) => (
              <VirtualModelCard
                key={model.id}
                model={model}
                onSelect={(id) => {
                  // TODO: Open detail/edit modal
                }}
                onDelete={handleDelete}
              />
            ))}
          </div>

          {/* Pagination */}
          {data.total > data.page_size && (
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-stone-600 dark:text-stone-400">
                共 {data.total} 个模型，第 {data.page} / {Math.ceil(data.total / data.page_size)} 页
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
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
            </svg>
            <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">暂无虚拟模型</h3>
            <p className="text-stone-600 dark:text-stone-400 mb-4">
              {searchQuery
                ? '没有找到匹配的模型，请调整筛选条件'
                : '创建您的第一个虚拟模型'}
            </p>
            {!searchQuery && (
              <button
                onClick={() => {
                  // TODO: Open create modal
                }}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors"
              >
                创建模型
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
