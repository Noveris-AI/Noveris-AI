/**
 * Gateway Overview Page
 *
 * Displays gateway statistics and usage metrics.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { gatewayClient } from '../api/gatewayClient'

export default function GatewayOverviewPage() {
  const navigate = useNavigate()
  const [dateRange, setDateRange] = useState<'24h' | '7d' | '30d'>('24h')

  // Calculate date range
  const getDateRange = () => {
    const end = new Date()
    const start = new Date()
    if (dateRange === '24h') {
      start.setHours(start.getHours() - 24)
    } else if (dateRange === '7d') {
      start.setDate(start.getDate() - 7)
    } else {
      start.setDate(start.getDate() - 30)
    }
    return {
      start_date: start.toISOString(),
      end_date: end.toISOString(),
    }
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ['gateway-overview', dateRange],
    queryFn: () => gatewayClient.getOverview(getDateRange()),
  })

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const formatCurrency = (num: number) => {
    return `$${num.toFixed(2)}`
  }

  const formatLatency = (ms: number) => {
    if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
    return `${ms.toFixed(0)}ms`
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">
            模型转发
          </h1>
          <p className="text-stone-600 dark:text-stone-400 mt-1">
            统一的 AI 模型网关，支持多种上游服务和智能路由
          </p>
        </div>
        <div className="flex items-center gap-2">
          {(['24h', '7d', '30d'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setDateRange(range)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                dateRange === range
                  ? 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300'
                  : 'text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-800'
              }`}
            >
              {range === '24h' ? '24小时' : range === '7d' ? '7天' : '30天'}
            </button>
          ))}
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
            加载数据失败，请稍后重试
          </p>
        </div>
      )}

      {data && (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
              <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
                {formatNumber(data.total_requests)}
              </div>
              <div className="text-sm text-stone-500 dark:text-stone-400">请求总数</div>
            </div>
            <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
              <div className={`text-2xl font-bold ${
                data.error_rate > 5 ? 'text-red-600 dark:text-red-400' :
                data.error_rate > 1 ? 'text-amber-600 dark:text-amber-400' :
                'text-green-600 dark:text-green-400'
              }`}>
                {data.error_rate.toFixed(2)}%
              </div>
              <div className="text-sm text-stone-500 dark:text-stone-400">
                错误率 ({formatNumber(data.total_errors)} 错误)
              </div>
            </div>
            <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
              <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
                {formatLatency(data.avg_latency_ms)}
              </div>
              <div className="text-sm text-stone-500 dark:text-stone-400">
                平均延迟 (P95: {formatLatency(data.p95_latency_ms)})
              </div>
            </div>
            <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4">
              <div className="text-2xl font-bold text-teal-600 dark:text-teal-400">
                {formatCurrency(data.total_cost_usd)}
              </div>
              <div className="text-sm text-stone-500 dark:text-stone-400">
                总费用 ({formatNumber(data.total_tokens)} tokens)
              </div>
            </div>
          </div>

          {/* Two Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Models */}
            <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
              <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">
                热门模型
              </h3>
              {data.top_models.length > 0 ? (
                <div className="space-y-3">
                  {data.top_models.slice(0, 5).map((item, index) => (
                    <div key={item.model} className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-stone-100 dark:bg-stone-700 text-xs font-medium text-stone-600 dark:text-stone-300">
                          {index + 1}
                        </span>
                        <span className="text-sm font-medium text-stone-900 dark:text-stone-100">
                          {item.model}
                        </span>
                      </div>
                      <span className="text-sm text-stone-500 dark:text-stone-400">
                        {formatNumber(item.count)} 次
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-stone-500 dark:text-stone-400">暂无数据</p>
              )}
            </div>

            {/* Top Upstreams */}
            <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
              <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">
                热门上游
              </h3>
              {data.top_upstreams.length > 0 ? (
                <div className="space-y-3">
                  {data.top_upstreams.slice(0, 5).map((item, index) => (
                    <div key={item.upstream} className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-stone-100 dark:bg-stone-700 text-xs font-medium text-stone-600 dark:text-stone-300">
                          {index + 1}
                        </span>
                        <span className="text-sm font-medium text-stone-900 dark:text-stone-100">
                          {item.upstream}
                        </span>
                      </div>
                      <span className="text-sm text-stone-500 dark:text-stone-400">
                        {formatNumber(item.count)} 次
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-stone-500 dark:text-stone-400">暂无数据</p>
              )}
            </div>
          </div>

          {/* Requests Chart */}
          <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">
              请求趋势
            </h3>
            {data.requests_by_hour.length > 0 ? (
              <div className="h-48 flex items-end gap-1">
                {data.requests_by_hour.map((item) => {
                  const maxCount = Math.max(...data.requests_by_hour.map(h => h.count))
                  const height = maxCount > 0 ? (item.count / maxCount) * 100 : 0
                  return (
                    <div
                      key={item.hour}
                      className="flex-1 bg-teal-500 dark:bg-teal-600 rounded-t hover:bg-teal-600 dark:hover:bg-teal-500 transition-colors cursor-pointer"
                      style={{ height: `${Math.max(height, item.count > 0 ? 4 : 0)}%` }}
                      title={`${item.hour}: ${item.count} 次请求`}
                    />
                  )
                })}
              </div>
            ) : (
              <p className="text-sm text-stone-500 dark:text-stone-400">暂无数据</p>
            )}
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <button
              onClick={() => navigate('upstreams')}
              className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 text-left hover:border-teal-300 dark:hover:border-teal-700 hover:shadow-lg transition-all"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                  <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
                  </svg>
                </div>
                <span className="font-medium text-stone-900 dark:text-stone-100">上游服务</span>
              </div>
              <p className="text-sm text-stone-500 dark:text-stone-400">配置 AI 提供商连接</p>
            </button>
            <button
              onClick={() => navigate('api-keys')}
              className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 text-left hover:border-teal-300 dark:hover:border-teal-700 hover:shadow-lg transition-all"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-lg">
                  <svg className="w-5 h-5 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                  </svg>
                </div>
                <span className="font-medium text-stone-900 dark:text-stone-100">API 密钥</span>
              </div>
              <p className="text-sm text-stone-500 dark:text-stone-400">创建和管理访问密钥</p>
            </button>
            <button
              onClick={() => navigate('routes')}
              className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 text-left hover:border-teal-300 dark:hover:border-teal-700 hover:shadow-lg transition-all"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                  <svg className="w-5 h-5 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                  </svg>
                </div>
                <span className="font-medium text-stone-900 dark:text-stone-100">路由策略</span>
              </div>
              <p className="text-sm text-stone-500 dark:text-stone-400">配置请求路由规则</p>
            </button>
            <button
              onClick={() => navigate('logs')}
              className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-4 text-left hover:border-teal-300 dark:hover:border-teal-700 hover:shadow-lg transition-all"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                  <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <span className="font-medium text-stone-900 dark:text-stone-100">请求日志</span>
              </div>
              <p className="text-sm text-stone-500 dark:text-stone-400">查看请求历史记录</p>
            </button>
          </div>
        </>
      )}
    </div>
  )
}
