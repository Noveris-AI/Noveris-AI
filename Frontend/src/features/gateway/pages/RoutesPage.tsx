/**
 * Gateway Routes Page
 *
 * Lists and manages routing policies.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { gatewayClient } from '../api/gatewayClient'
import type { Route } from '../api/gatewayTypes'
import { RouteCard } from '../components/RouteCard'

export default function RoutesPage() {
  const queryClient = useQueryClient()

  // State
  const [page, setPage] = useState(1)

  // Fetch routes
  const { data, isLoading, error } = useQuery({
    queryKey: ['gateway-routes', page],
    queryFn: () =>
      gatewayClient.listRoutes({
        page,
        page_size: 12,
      }),
  })

  // Delete route mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayClient.deleteRoute(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gateway-routes'] })
    },
  })

  const handleDelete = (id: string) => {
    const route = data?.items.find(r => r.id === id)
    if (route && window.confirm(`确定要删除路由 "${route.name}" 吗？`)) {
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
    enabled: data.items.filter(r => r.enabled).length,
    withFallback: data.items.filter(r => r.action.fallback_upstreams && r.action.fallback_upstreams.length > 0).length,
  } : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            路由策略
          </h1>
          <p className="text-stone-600 dark:text-stone-400 mt-1">
            配置请求如何路由到上游服务
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
          创建路由
        </button>
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-200 dark:border-blue-800 p-4">
        <div className="flex items-start gap-3">
          <svg className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-blue-700 dark:text-blue-300">
            路由按优先级顺序评估（数字越小优先级越高）。第一个匹配的路由将被使用。
          </p>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
              {stats.total}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">路由总数</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.enabled}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">已启用</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-teal-600 dark:text-teal-400">
              {stats.withFallback}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">配置备用</div>
          </div>
        </div>
      )}

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
            加载路由失败，请稍后重试
          </p>
        </div>
      )}

      {/* Routes Grid */}
      {data && data.items.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.items.map((route) => (
              <RouteCard
                key={route.id}
                route={route}
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
                共 {data.total} 个路由，第 {data.page} / {Math.ceil(data.total / data.page_size)} 页
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
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
            <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">暂无路由策略</h3>
            <p className="text-stone-600 dark:text-stone-400 mb-4">
              创建您的第一个路由策略
            </p>
            <button
              onClick={() => {
                // TODO: Open create modal
              }}
              className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors"
            >
              创建路由
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
