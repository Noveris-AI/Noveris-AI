/**
 * Gateway API Keys Page
 *
 * Lists and manages API keys for external access to the gateway.
 */

import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { gatewayClient } from '../api/gatewayClient'
import type { APIKey, APIKeyCreateResponse } from '../api/gatewayTypes'
import { APIKeyCard } from '../components/APIKeyCard'

export default function APIKeysPage() {
  const queryClient = useQueryClient()

  // State
  const [page, setPage] = useState(1)
  const [searchQuery, setSearchQuery] = useState('')
  const [newKeyResponse, setNewKeyResponse] = useState<APIKeyCreateResponse | null>(null)
  const [keyCopied, setKeyCopied] = useState(false)

  // Fetch API keys
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['gateway-api-keys', page, searchQuery],
    queryFn: () =>
      gatewayClient.listAPIKeys({
        page,
        page_size: 12,
        search: searchQuery || undefined,
      }),
  })

  // Create API key mutation
  const createMutation = useMutation({
    mutationFn: gatewayClient.createAPIKey.bind(gatewayClient),
    onSuccess: (response) => {
      setNewKeyResponse(response)
      queryClient.invalidateQueries({ queryKey: ['gateway-api-keys'] })
    },
  })

  // Delete API key mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayClient.deleteAPIKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gateway-api-keys'] })
    },
  })

  // Regenerate API key mutation
  const regenerateMutation = useMutation({
    mutationFn: (id: string) => gatewayClient.regenerateAPIKey(id),
    onSuccess: (response) => {
      setNewKeyResponse(response)
      queryClient.invalidateQueries({ queryKey: ['gateway-api-keys'] })
    },
  })

  const handleSearch = () => {
    setPage(1)
    refetch()
  }

  const handleDelete = (id: string) => {
    const apiKey = data?.items.find(k => k.id === id)
    if (apiKey && window.confirm(`确定要删除 API 密钥 "${apiKey.name}" 吗？此操作无法撤销。`)) {
      deleteMutation.mutate(id)
    }
  }

  const handleRegenerate = (id: string) => {
    const apiKey = data?.items.find(k => k.id === id)
    if (apiKey && window.confirm(`确定要重新生成 API 密钥 "${apiKey.name}" 吗？旧密钥将立即失效。`)) {
      regenerateMutation.mutate(id)
    }
  }

  const handleCopyKey = () => {
    if (newKeyResponse?.key) {
      navigator.clipboard.writeText(newKeyResponse.key)
      setKeyCopied(true)
      setTimeout(() => setKeyCopied(false), 2000)
    }
  }

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Calculate stats
  const stats = data ? {
    total: data.total,
    enabled: data.items.filter(k => k.enabled).length,
    expired: data.items.filter(k => k.expires_at && new Date(k.expires_at) < new Date()).length,
    active: data.items.filter(k => k.last_used_at).length,
  } : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            API 密钥
          </h1>
          <p className="text-stone-600 dark:text-stone-400 mt-1">
            创建和管理用于访问网关的 API 密钥
          </p>
        </div>
        <button
          onClick={() => {
            // Quick create a key with default settings
            createMutation.mutate({ name: `key-${Date.now()}` })
          }}
          disabled={createMutation.isPending}
          className="px-4 py-2 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          创建密钥
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
              {stats.total}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">密钥总数</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.enabled}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">已启用</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {stats.expired}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">已过期</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-teal-600 dark:text-teal-400">
              {stats.active}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">活跃使用</div>
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
            placeholder="搜索密钥名称..."
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
            加载 API 密钥失败，请稍后重试
          </p>
        </div>
      )}

      {/* API Keys Grid */}
      {data && data.items.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.items.map((apiKey) => (
              <APIKeyCard
                key={apiKey.id}
                apiKey={apiKey}
                onSelect={(id) => {
                  // TODO: Open detail/edit modal
                }}
                onDelete={handleDelete}
                onRegenerate={handleRegenerate}
              />
            ))}
          </div>

          {/* Pagination */}
          {data.total > data.page_size && (
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-stone-600 dark:text-stone-400">
                共 {data.total} 个密钥，第 {data.page} / {Math.ceil(data.total / data.page_size)} 页
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
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
            <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">暂无 API 密钥</h3>
            <p className="text-stone-600 dark:text-stone-400 mb-4">
              {searchQuery
                ? '没有找到匹配的密钥，请调整筛选条件'
                : '创建您的第一个 API 密钥'}
            </p>
            {!searchQuery && (
              <button
                onClick={() => createMutation.mutate({ name: `key-${Date.now()}` })}
                disabled={createMutation.isPending}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors"
              >
                创建密钥
              </button>
            )}
          </div>
        </div>
      )}

      {/* New Key Modal */}
      {newKeyResponse && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-lg mx-4 bg-white dark:bg-stone-800 rounded-xl shadow-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
                API 密钥已创建
              </h2>
            </div>

            <div className="bg-amber-50 dark:bg-amber-900/20 rounded-lg p-3 mb-4">
              <p className="text-sm text-amber-700 dark:text-amber-300">
                请立即复制您的 API 密钥。关闭此窗口后将无法再次查看完整密钥！
              </p>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                您的 API 密钥
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={newKeyResponse.key}
                  className="flex-1 px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-stone-50 dark:bg-stone-900 font-mono text-sm text-stone-900 dark:text-stone-100"
                />
                <button
                  onClick={handleCopyKey}
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors"
                >
                  {keyCopied ? '已复制!' : '复制'}
                </button>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setNewKeyResponse(null)}
                className="px-4 py-2 border border-stone-300 dark:border-stone-600 text-stone-700 dark:text-stone-300 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors"
              >
                完成
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
