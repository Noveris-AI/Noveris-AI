import { useEffect, useState } from 'react'
import { modelMarketClient } from '../api/modelMarketClient'
import type { SyncLog, SyncType, SyncSource } from '../api/modelMarketTypes'

interface SyncStatusPanelProps {
  onSyncChange?: () => void
}

const SYNC_STATUS_CONFIG: Record<SyncLog['status'], { color: string; label: string }> = {
  pending: { color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300', label: '等待中' },
  running: { color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300', label: '同步中' },
  completed: { color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300', label: '已完成' },
  failed: { color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300', label: '失败' },
  cancelled: { color: 'bg-stone-100 text-stone-800 dark:bg-stone-700 dark:text-stone-300', label: '已取消' },
}

export function SyncStatusPanel({ onSyncChange }: SyncStatusPanelProps) {
  const [syncStatus, setSyncStatus] = useState<SyncLog | null>(null)
  const [triggering, setTriggering] = useState(false)
  const [showTriggerDialog, setShowTriggerDialog] = useState(false)

  const fetchSyncStatus = async () => {
    try {
      const status = await modelMarketClient.getLatestSyncStatus()
      setSyncStatus(status)
    } catch (error) {
      console.error('Failed to fetch sync status:', error)
    }
  }

  useEffect(() => {
    fetchSyncStatus()

    // Poll for updates when syncing
    const interval = setInterval(() => {
      if (syncStatus?.status === 'running' || syncStatus?.status === 'pending') {
        fetchSyncStatus()
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [syncStatus?.status])

  const handleTriggerSync = async (syncType: SyncType, source: SyncSource) => {
    setTriggering(true)
    try {
      await modelMarketClient.triggerSync({ sync_type: syncType, source })
      await fetchSyncStatus()
      setShowTriggerDialog(false)
      onSyncChange?.()
    } catch (error) {
      console.error('Failed to trigger sync:', error)
      alert(error instanceof Error ? error.message : '触发同步失败')
    } finally {
      setTriggering(false)
    }
  }

  const handleCancelSync = async () => {
    if (!syncStatus) return

    try {
      await modelMarketClient.cancelSync(syncStatus.id)
      await fetchSyncStatus()
      onSyncChange?.()
    } catch (error) {
      console.error('Failed to cancel sync:', error)
      alert(error instanceof Error ? error.message : '取消同步失败')
    }
  }

  const formatDuration = (start: string | null, end: string | null) => {
    if (!start) return '-'
    const startDate = new Date(start)
    const endDate = end ? new Date(end) : new Date()
    const diffMs = endDate.getTime() - startDate.getTime()
    const diffSecs = Math.floor(diffMs / 1000)
    const diffMins = Math.floor(diffSecs / 60)
    const diffHours = Math.floor(diffMins / 60)

    if (diffHours > 0) return `${diffHours}小时${diffMins % 60}分钟`
    if (diffMins > 0) return `${diffMins}分钟${diffSecs % 60}秒`
    return `${diffSecs}秒`
  }

  const statusInfo = syncStatus ? SYNC_STATUS_CONFIG[syncStatus.status] : null
  const isSyncing = syncStatus?.status === 'running' || syncStatus?.status === 'pending'

  return (
    <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-stone-900 dark:text-stone-100">同步状态</h3>
        <button
          onClick={() => setShowTriggerDialog(!showTriggerDialog)}
          disabled={isSyncing || triggering}
          className="px-3 py-1.5 text-sm bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg transition-colors disabled:cursor-not-allowed"
        >
          {triggering ? '处理中...' : '触发同步'}
        </button>
      </div>

      {/* Trigger Dialog */}
      {showTriggerDialog && (
        <div className="mb-4 p-3 bg-stone-50 dark:bg-stone-700 rounded-lg">
          <p className="text-sm text-stone-700 dark:text-stone-300 mb-3">选择同步类型和数据源：</p>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => handleTriggerSync('full', 'huggingface')}
              disabled={triggering}
              className="px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-600 transition-colors disabled:opacity-50"
            >
              全量同步 (HF)
            </button>
            <button
              onClick={() => handleTriggerSync('incremental', 'huggingface')}
              disabled={triggering}
              className="px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-600 transition-colors disabled:opacity-50"
            >
              增量同步 (HF)
            </button>
            <button
              onClick={() => handleTriggerSync('full', 'hf-mirror')}
              disabled={triggering}
              className="px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-600 transition-colors disabled:opacity-50"
            >
              全量同步 (Mirror)
            </button>
            <button
              onClick={() => handleTriggerSync('incremental', 'hf-mirror')}
              disabled={triggering}
              className="px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-600 transition-colors disabled:opacity-50"
            >
              增量同步 (Mirror)
            </button>
          </div>
          <p className="text-xs text-stone-500 dark:text-stone-400 mt-2">
            全量同步可能需要数小时，增量同步只同步更新的模型
          </p>
        </div>
      )}

      {/* Sync Status */}
      {syncStatus ? (
        <div className="space-y-3">
          {/* Status Badge */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {statusInfo && (
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusInfo.color}`}>
                  {statusInfo.label}
                </span>
              )}
              <span className="text-sm text-stone-600 dark:text-stone-400">
                {syncStatus.sync_type === 'full' ? '全量同步' : '增量同步'}
              </span>
              <span className="text-xs text-stone-500 dark:text-stone-500">
                ({syncStatus.source === 'huggingface' ? 'HF Official' : 'HF Mirror'})
              </span>
            </div>
            {isSyncing && (
              <button
                onClick={handleCancelSync}
                className="px-2 py-1 text-xs text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 transition-colors"
              >
                取消
              </button>
            )}
          </div>

          {/* Progress Bar */}
          {isSyncing && syncStatus.progress_percentage > 0 && (
            <div>
              <div className="flex justify-between text-xs text-stone-600 dark:text-stone-400 mb-1">
                <span>进度</span>
                <span>{syncStatus.progress_percentage}%</span>
              </div>
              <div className="h-2 bg-stone-200 dark:bg-stone-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-teal-600 transition-all duration-300"
                  style={{ width: `${syncStatus.progress_percentage}%` }}
                />
              </div>
              {syncStatus.current_page > 0 && syncStatus.total_pages > 0 && (
                <p className="text-xs text-stone-500 dark:text-stone-500 mt-1">
                  第 {syncStatus.current_page} / {syncStatus.total_pages} 页
                </p>
              )}
            </div>
          )}

          {/* Stats */}
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 bg-stone-50 dark:bg-stone-700 rounded-lg">
              <p className="text-lg font-semibold text-teal-600 dark:text-teal-400">
                {syncStatus.synced_models}
              </p>
              <p className="text-xs text-stone-600 dark:text-stone-400">已同步</p>
            </div>
            <div className="p-2 bg-stone-50 dark:bg-stone-700 rounded-lg">
              <p className="text-lg font-semibold text-blue-600 dark:text-blue-400">
                {syncStatus.updated_models}
              </p>
              <p className="text-xs text-stone-600 dark:text-stone-400">已更新</p>
            </div>
            <div className="p-2 bg-stone-50 dark:bg-stone-700 rounded-lg">
              <p className="text-lg font-semibold text-red-600 dark:text-red-400">
                {syncStatus.failed_models}
              </p>
              <p className="text-xs text-stone-600 dark:text-stone-400">失败</p>
            </div>
          </div>

          {/* Error Message */}
          {syncStatus.error_message && (
            <div className="p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-xs text-red-600 dark:text-red-400">{syncStatus.error_message}</p>
            </div>
          )}

          {/* Time Info */}
          <div className="flex justify-between text-xs text-stone-500 dark:text-stone-500">
            <span>开始: {syncStatus.started_at ? new Date(syncStatus.started_at).toLocaleString('zh-CN') : '-'}</span>
            <span>用时: {formatDuration(syncStatus.started_at, syncStatus.completed_at)}</span>
          </div>
        </div>
      ) : (
        <div className="text-center py-4 text-stone-500 dark:text-stone-400 text-sm">
          暂无同步记录
        </div>
      )}
    </div>
  )
}
