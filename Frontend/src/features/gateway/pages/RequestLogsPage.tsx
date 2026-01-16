/**
 * Gateway Request Logs Page
 *
 * Displays request history and allows searching/filtering.
 */

import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { gatewayClient } from '../api/gatewayClient'
import type { RequestLog } from '../api/gatewayTypes'
import { HTTPStatusBadge } from '../components/StatusBadge'

// Status filter options
const statusOptions = [
  { value: '', label: '全部状态' },
  { value: '200', label: '200 成功' },
  { value: '400', label: '400 请求错误' },
  { value: '401', label: '401 未授权' },
  { value: '429', label: '429 限流' },
  { value: '500', label: '500 服务器错误' },
]

export default function RequestLogsPage() {
  // State
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({
    request_id: '',
    endpoint: '',
    virtual_model: '',
    status_code: '',
    error_type: '',
    start_date: '',
    end_date: '',
  })
  const [selectedLog, setSelectedLog] = useState<RequestLog | null>(null)
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false)

  const statusDropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (statusDropdownRef.current && !statusDropdownRef.current.contains(event.target as Node)) {
        setStatusDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Fetch request logs
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['gateway-request-logs', page, filters],
    queryFn: () =>
      gatewayClient.listRequestLogs({
        page,
        page_size: 50,
        request_id: filters.request_id || undefined,
        endpoint: filters.endpoint || undefined,
        virtual_model: filters.virtual_model || undefined,
        status_code: filters.status_code ? parseInt(filters.status_code) : undefined,
        error_type: filters.error_type || undefined,
        start_date: filters.start_date || undefined,
        end_date: filters.end_date || undefined,
      }),
  })

  // Fetch single log details
  const { data: logDetail } = useQuery({
    queryKey: ['gateway-request-log', selectedLog?.id],
    queryFn: () => gatewayClient.getRequestLog(selectedLog!.id),
    enabled: !!selectedLog,
  })

  const formatLatency = (ms?: number) => {
    if (ms === undefined) return '-'
    if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`
    return `${ms.toFixed(0)}ms`
  }

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString('zh-CN')
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const handleSearch = () => {
    setPage(1)
    refetch()
  }

  const handleClearFilters = () => {
    setFilters({
      request_id: '',
      endpoint: '',
      virtual_model: '',
      status_code: '',
      error_type: '',
      start_date: '',
      end_date: '',
    })
    setPage(1)
  }

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const hasActiveFilters = filters.request_id || filters.endpoint || filters.virtual_model ||
    filters.status_code || filters.error_type || filters.start_date || filters.end_date

  // Calculate stats from current page
  const stats = data ? {
    total: data.total,
    success: data.items.filter(l => l.status_code && l.status_code >= 200 && l.status_code < 300).length,
    errors: data.items.filter(l => l.status_code && l.status_code >= 400).length,
    avgLatency: data.items.length > 0
      ? data.items.reduce((sum, l) => sum + (l.latency_ms || 0), 0) / data.items.length
      : 0,
  } : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            请求日志
          </h1>
          <p className="text-stone-600 dark:text-stone-400 mt-1">
            查看和分析网关请求历史
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isLoading}
          className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-700 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          <svg className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          刷新
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
              {formatNumber(stats.total)}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">总请求数</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.success}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">本页成功</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {stats.errors}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">本页错误</div>
          </div>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
            <div className="text-2xl font-bold text-teal-600 dark:text-teal-400">
              {formatLatency(stats.avgLatency)}
            </div>
            <div className="text-sm text-stone-500 dark:text-stone-400">平均延迟</div>
          </div>
        </div>
      )}

      {/* Filters Bar */}
      <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 space-y-4">
        {/* First Row: Search Inputs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <input
            type="text"
            placeholder="请求 ID..."
            value={filters.request_id}
            onChange={(e) => setFilters({ ...filters, request_id: e.target.value })}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
          />
          <input
            type="text"
            placeholder="端点..."
            value={filters.endpoint}
            onChange={(e) => setFilters({ ...filters, endpoint: e.target.value })}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
          />
          <input
            type="text"
            placeholder="模型..."
            value={filters.virtual_model}
            onChange={(e) => setFilters({ ...filters, virtual_model: e.target.value })}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
          />

          {/* Status Dropdown */}
          <div ref={statusDropdownRef} className="relative">
            <button
              onClick={() => setStatusDropdownOpen(!statusDropdownOpen)}
              className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center justify-between"
            >
              <span>
                {filters.status_code
                  ? statusOptions.find(o => o.value === filters.status_code)?.label
                  : '全部状态'}
              </span>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {statusDropdownOpen && (
              <div className="absolute left-0 right-0 mt-2 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10">
                {statusOptions.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => {
                      setFilters({ ...filters, status_code: option.value })
                      setStatusDropdownOpen(false)
                      setPage(1)
                    }}
                    className={`w-full px-4 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors ${
                      filters.status_code === option.value ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-700 dark:text-stone-300'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Second Row: Date Range and Actions */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-sm text-stone-500 dark:text-stone-400">从</span>
            <input
              type="datetime-local"
              value={filters.start_date}
              onChange={(e) => setFilters({ ...filters, start_date: e.target.value })}
              className="px-3 py-1.5 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-stone-500 dark:text-stone-400">至</span>
            <input
              type="datetime-local"
              value={filters.end_date}
              onChange={(e) => setFilters({ ...filters, end_date: e.target.value })}
              className="px-3 py-1.5 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
            />
          </div>

          <div className="flex-1" />

          <button
            onClick={handleSearch}
            disabled={isLoading}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed"
          >
            搜索
          </button>

          {hasActiveFilters && (
            <button
              onClick={handleClearFilters}
              className="px-3 py-2 text-sm text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 transition-colors"
            >
              清除筛选
            </button>
          )}
        </div>
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
            加载请求日志失败，请稍后重试
          </p>
        </div>
      )}

      {/* Logs Table */}
      {data && data.items.length > 0 && (
        <>
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-stone-200 dark:divide-stone-700">
                <thead className="bg-stone-50 dark:bg-stone-900/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-stone-500 dark:text-stone-400">
                      时间
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-stone-500 dark:text-stone-400">
                      请求 ID
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-stone-500 dark:text-stone-400">
                      端点
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-stone-500 dark:text-stone-400">
                      模型
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-stone-500 dark:text-stone-400">
                      状态
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-stone-500 dark:text-stone-400">
                      延迟
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-stone-500 dark:text-stone-400">
                      Tokens
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200 dark:divide-stone-700">
                  {data.items.map((log) => (
                    <tr
                      key={log.id}
                      onClick={() => setSelectedLog(log)}
                      className="hover:bg-stone-50 dark:hover:bg-stone-700/50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 text-sm text-stone-500 dark:text-stone-400 whitespace-nowrap">
                        {formatTimestamp(log.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <code className="text-xs font-mono text-stone-600 dark:text-stone-400 bg-stone-100 dark:bg-stone-900 px-1.5 py-0.5 rounded">
                          {log.request_id.slice(0, 8)}...
                        </code>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span className="text-stone-500 dark:text-stone-400 mr-1 font-medium">{log.method}</span>
                        <span className="text-stone-900 dark:text-stone-100">{log.endpoint}</span>
                      </td>
                      <td className="px-4 py-3 text-sm text-stone-600 dark:text-stone-400">
                        {log.virtual_model || '-'}
                      </td>
                      <td className="px-4 py-3">
                        <HTTPStatusBadge status={log.status_code} />
                      </td>
                      <td className="px-4 py-3 text-sm text-stone-600 dark:text-stone-400">
                        {formatLatency(log.latency_ms)}
                      </td>
                      <td className="px-4 py-3 text-sm text-stone-600 dark:text-stone-400">
                        {log.total_tokens ? log.total_tokens.toLocaleString() : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {data.total > data.page_size && (
              <div className="flex items-center justify-between border-t border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-900/50 px-4 py-3">
                <p className="text-sm text-stone-600 dark:text-stone-400">
                  共 {data.total.toLocaleString()} 条记录，第 {data.page} / {Math.ceil(data.total / data.page_size)} 页
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handlePageChange(page - 1)}
                    disabled={page <= 1 || isLoading}
                    className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    上一页
                  </button>
                  <button
                    onClick={() => handlePageChange(page + 1)}
                    disabled={page >= Math.ceil(data.total / data.page_size) || isLoading}
                    className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    下一页
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Empty state */}
      {data && data.items.length === 0 && (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <svg className="w-16 h-16 text-stone-300 dark:text-stone-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">暂无请求日志</h3>
            <p className="text-stone-600 dark:text-stone-400">
              {hasActiveFilters
                ? '没有找到匹配的日志，请调整筛选条件'
                : '当有请求通过网关时，日志将显示在这里'}
            </p>
          </div>
        </div>
      )}

      {/* Log Detail Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-2xl max-h-[80vh] overflow-auto mx-4 bg-white dark:bg-stone-800 rounded-xl shadow-xl">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-stone-200 dark:border-stone-700">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                  <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
                  请求详情
                </h2>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="p-1 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-6">
              {/* Basic Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-stone-500 dark:text-stone-400 mb-1">请求 ID</label>
                  <p className="text-sm text-stone-900 dark:text-stone-100 font-mono bg-stone-100 dark:bg-stone-900 px-2 py-1 rounded break-all">
                    {selectedLog.request_id}
                  </p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-500 dark:text-stone-400 mb-1">追踪 ID</label>
                  <p className="text-sm text-stone-900 dark:text-stone-100 font-mono bg-stone-100 dark:bg-stone-900 px-2 py-1 rounded">
                    {selectedLog.trace_id || '-'}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-stone-500 dark:text-stone-400 mb-1">端点</label>
                  <p className="text-sm text-stone-900 dark:text-stone-100">
                    <span className="font-medium text-stone-500 dark:text-stone-400 mr-1">{selectedLog.method}</span>
                    {selectedLog.endpoint}
                  </p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-500 dark:text-stone-400 mb-1">状态码</label>
                  <HTTPStatusBadge status={selectedLog.status_code} />
                </div>
              </div>

              {/* Model Info */}
              <div className="bg-stone-50 dark:bg-stone-900/50 rounded-lg p-4">
                <h4 className="text-sm font-medium text-stone-900 dark:text-stone-100 mb-3">模型信息</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-stone-500 dark:text-stone-400 mb-1">虚拟模型</label>
                    <p className="text-sm text-stone-900 dark:text-stone-100">{selectedLog.virtual_model || '-'}</p>
                  </div>
                  <div>
                    <label className="block text-xs text-stone-500 dark:text-stone-400 mb-1">上游模型</label>
                    <p className="text-sm text-stone-900 dark:text-stone-100">{selectedLog.upstream_model || '-'}</p>
                  </div>
                </div>
              </div>

              {/* Latency */}
              <div className="bg-stone-50 dark:bg-stone-900/50 rounded-lg p-4">
                <h4 className="text-sm font-medium text-stone-900 dark:text-stone-100 mb-3">延迟指标</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs text-stone-500 dark:text-stone-400 mb-1">总延迟</label>
                    <p className="text-sm font-medium text-stone-900 dark:text-stone-100">{formatLatency(selectedLog.latency_ms)}</p>
                  </div>
                  <div>
                    <label className="block text-xs text-stone-500 dark:text-stone-400 mb-1">上游延迟</label>
                    <p className="text-sm font-medium text-stone-900 dark:text-stone-100">{formatLatency(selectedLog.upstream_latency_ms)}</p>
                  </div>
                  <div>
                    <label className="block text-xs text-stone-500 dark:text-stone-400 mb-1">首 Token 时间</label>
                    <p className="text-sm font-medium text-stone-900 dark:text-stone-100">{formatLatency(selectedLog.time_to_first_token_ms)}</p>
                  </div>
                </div>
              </div>

              {/* Tokens & Cost */}
              <div className="bg-stone-50 dark:bg-stone-900/50 rounded-lg p-4">
                <h4 className="text-sm font-medium text-stone-900 dark:text-stone-100 mb-3">用量与费用</h4>
                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <label className="block text-xs text-stone-500 dark:text-stone-400 mb-1">输入 Tokens</label>
                    <p className="text-sm font-medium text-stone-900 dark:text-stone-100">{selectedLog.prompt_tokens?.toLocaleString() || '-'}</p>
                  </div>
                  <div>
                    <label className="block text-xs text-stone-500 dark:text-stone-400 mb-1">输出 Tokens</label>
                    <p className="text-sm font-medium text-stone-900 dark:text-stone-100">{selectedLog.completion_tokens?.toLocaleString() || '-'}</p>
                  </div>
                  <div>
                    <label className="block text-xs text-stone-500 dark:text-stone-400 mb-1">总 Tokens</label>
                    <p className="text-sm font-medium text-stone-900 dark:text-stone-100">{selectedLog.total_tokens?.toLocaleString() || '-'}</p>
                  </div>
                  <div>
                    <label className="block text-xs text-stone-500 dark:text-stone-400 mb-1">
                      费用 {selectedLog.estimated_cost && '(估算)'}
                    </label>
                    <p className="text-sm font-medium text-teal-600 dark:text-teal-400">
                      {selectedLog.cost_usd !== undefined ? `$${selectedLog.cost_usd.toFixed(6)}` : '-'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Error */}
              {selectedLog.error_type && (
                <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4 border border-red-200 dark:border-red-800">
                  <h4 className="text-sm font-medium text-red-700 dark:text-red-300 mb-2">错误信息</h4>
                  <p className="text-sm text-red-600 dark:text-red-400">
                    <span className="font-medium">{selectedLog.error_type}</span>: {selectedLog.error_message}
                  </p>
                </div>
              )}

              {/* Timestamp */}
              <div>
                <label className="block text-xs font-medium text-stone-500 dark:text-stone-400 mb-1">请求时间</label>
                <p className="text-sm text-stone-900 dark:text-stone-100">{formatTimestamp(selectedLog.created_at)}</p>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end gap-3 p-6 border-t border-stone-200 dark:border-stone-700">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-2 border border-stone-300 dark:border-stone-600 text-stone-700 dark:text-stone-300 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
