/**
 * Log Viewer Component
 *
 * Displays deployment and service logs with syntax highlighting.
 */

import { useState, useEffect, useRef } from 'react'
import type { DeploymentLog, LogLine } from '../api/deploymentTypes'

interface DeploymentLogViewerProps {
  logs: DeploymentLog[]
  loading?: boolean
  onRefresh?: () => void
}

const levelColors: Record<string, string> = {
  DEBUG: 'text-stone-400',
  INFO: 'text-blue-500',
  WARNING: 'text-amber-500',
  ERROR: 'text-red-500',
  CRITICAL: 'text-red-600 font-bold',
}

export function DeploymentLogViewer({ logs, loading, onRefresh }: DeploymentLogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-900">
        <div className="flex items-center gap-3">
          <span className="text-sm text-stone-600 dark:text-stone-400">
            {logs.length} 条记录
          </span>
          {loading && (
            <div className="flex items-center gap-2 text-sm text-teal-600">
              <div className="animate-spin rounded-full h-3 w-3 border-b border-teal-600"></div>
              加载中
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-stone-600 dark:text-stone-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="w-4 h-4 text-teal-600 rounded"
            />
            自动滚动
          </label>
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              className="p-1.5 text-stone-500 hover:text-stone-700 dark:text-stone-400 dark:hover:text-stone-200 transition-colors disabled:opacity-50"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Log Content */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-stone-900 text-stone-100 font-mono text-xs p-3"
      >
        {logs.length === 0 ? (
          <div className="text-stone-500 text-center py-8">暂无日志</div>
        ) : (
          <div className="space-y-1">
            {logs.map((log) => (
              <div key={log.id} className="flex gap-3 hover:bg-stone-800 px-2 py-0.5 rounded">
                <span className="text-stone-500 flex-shrink-0">
                  {new Date(log.created_at).toLocaleTimeString()}
                </span>
                <span className={`flex-shrink-0 w-16 ${levelColors[log.level] || 'text-stone-400'}`}>
                  [{log.level}]
                </span>
                {log.source && (
                  <span className="text-purple-400 flex-shrink-0">
                    [{log.source}]
                  </span>
                )}
                <span className="flex-1 break-all">{log.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Service Log Viewer (stdout/stderr)
interface ServiceLogViewerProps {
  lines: LogLine[]
  loading?: boolean
  onRefresh?: () => void
}

export function ServiceLogViewer({ lines, loading, onRefresh }: ServiceLogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [lines, autoScroll])

  const getLineColor = (source: string) => {
    if (source === 'stderr') return 'text-red-400'
    return 'text-stone-100'
  }

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-900">
        <div className="flex items-center gap-3">
          <span className="text-sm text-stone-600 dark:text-stone-400">
            服务日志 · {lines.length} 行
          </span>
          {loading && (
            <div className="flex items-center gap-2 text-sm text-teal-600">
              <div className="animate-spin rounded-full h-3 w-3 border-b border-teal-600"></div>
              加载中
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-stone-600 dark:text-stone-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="w-4 h-4 text-teal-600 rounded"
            />
            自动滚动
          </label>
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              className="p-1.5 text-stone-500 hover:text-stone-700 dark:text-stone-400 dark:hover:text-stone-200 transition-colors disabled:opacity-50"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Log Content */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-stone-900 text-stone-100 font-mono text-xs p-3"
      >
        {lines.length === 0 ? (
          <div className="text-stone-500 text-center py-8">暂无日志</div>
        ) : (
          <div className="space-y-0.5">
            {lines.map((line, index) => (
              <div key={index} className={`${getLineColor(line.source)} hover:bg-stone-800 px-2 py-0.5 rounded`}>
                {line.timestamp && (
                  <span className="text-stone-500 mr-3">
                    {new Date(line.timestamp).toLocaleTimeString()}
                  </span>
                )}
                <span className="break-all">{line.content}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
