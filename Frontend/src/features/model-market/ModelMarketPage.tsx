import { useState, useEffect, useRef } from 'react'
import { modelMarketClient } from './api/modelMarketClient'
import type { ModelCard, SortBy, AIRecommendConfig, ModelCardDetail } from './api/modelMarketTypes'
import { ModelCardComponent } from './components/ModelCard'
import { Pagination } from './components/Pagination'
import { AIRecommendChat } from './components/AIRecommendChat'

export function ModelMarketPage() {
  // State
  const [models, setModels] = useState<ModelCard[]>([])
  const [total, setTotal] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)

  // Filter options
  const [categories, setCategories] = useState<Array<{ category: string; count: number }>>([])

  // Current filters
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState<SortBy>('last_modified')
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])

  // Dropdown states
  const [sortDropdownOpen, setSortDropdownOpen] = useState(false)
  const [categoryDropdownOpen, setCategoryDropdownOpen] = useState(false)
  const [configDropdownOpen, setConfigDropdownOpen] = useState(false)

  // Sync state
  const [syncStatus, setSyncStatus] = useState<any>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncStartTime, setSyncStartTime] = useState<number | null>(null)
  const [syncTimedOut, setSyncTimedOut] = useState(false)

  // AI Config state
  const [aiConfig, setAiConfig] = useState<AIRecommendConfig | null>(null)
  const [aiProvider, setAiProvider] = useState('openai')
  const [aiModelName, setAiModelName] = useState('')
  const [aiEndpointUrl, setAiEndpointUrl] = useState('')
  const [aiApiKey, setAiApiKey] = useState('')
  const [aiSaving, setAiSaving] = useState(false)
  const [aiMessage, setAiMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Selected model detail state
  const [selectedModelDetail, setSelectedModelDetail] = useState<ModelCardDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Sync message state
  const [syncMessage, setSyncMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const sortDropdownRef = useRef<HTMLDivElement>(null)
  const categoryDropdownRef = useRef<HTMLDivElement>(null)
  const configDropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sortDropdownRef.current && !sortDropdownRef.current.contains(event.target as Node)) {
        setSortDropdownOpen(false)
      }
      if (categoryDropdownRef.current && !categoryDropdownRef.current.contains(event.target as Node)) {
        setCategoryDropdownOpen(false)
      }
      if (configDropdownRef.current && !configDropdownRef.current.contains(event.target as Node)) {
        setConfigDropdownOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Fetch models
  const fetchModels = async (page: number = currentPage) => {
    setLoading(true)
    try {
      const response = await modelMarketClient.searchModels({
        query: searchQuery || undefined,
        categories: selectedCategories.length > 0 ? selectedCategories : undefined,
        sort_by: sortBy,
        sort_order: 'desc',
        page,
        page_size: 20,
      })

      setModels(response.models)
      setTotal(response.total)
      setTotalPages(response.total_pages)
      setCurrentPage(response.page)
    } catch (error) {
      console.error('Failed to fetch models:', error)
    } finally {
      setLoading(false)
      setInitialLoading(false)
    }
  }

  // Fetch filter options
  const fetchFilterOptions = async () => {
    try {
      const [categoriesData, syncData, aiConfigData] = await Promise.all([
        modelMarketClient.getCategories(),
        modelMarketClient.getLatestSyncStatus(),
        modelMarketClient.getAIConfig(),
      ])
      setCategories(categoriesData)

      // Load AI config if exists
      if (aiConfigData) {
        setAiConfig(aiConfigData)
        setAiProvider(aiConfigData.provider)
        setAiModelName(aiConfigData.model_name)
        setAiEndpointUrl(aiConfigData.endpoint_url)
        setAiApiKey(aiConfigData.api_key || '')
      }

      // Track sync start time for timeout checking
      const isPendingOrRunning = syncData?.status === 'pending' || syncData?.status === 'running'
      const wasPendingOrRunning = syncStatus?.status === 'pending' || syncStatus?.status === 'running'

      if (isPendingOrRunning && !syncStartTime) {
        // Sync is pending/running and we don't have a start time yet
        setSyncStartTime(Date.now())
        setSyncTimedOut(false)
      } else if (!isPendingOrRunning) {
        // Sync is no longer running, clear timeout state
        setSyncStartTime(null)
        setSyncTimedOut(false)
      }

      setSyncStatus(syncData)
    } catch (error) {
      console.error('Failed to fetch filter options:', error)
    }
  }

  // Initial load
  useEffect(() => {
    fetchModels()
    fetchFilterOptions()
  }, [])

  // Poll sync status when there's a running/pending sync
  useEffect(() => {
    if (syncStatus?.status === 'running' || syncStatus?.status === 'pending') {
      const interval = setInterval(() => {
        fetchFilterOptions()
      }, 5000) // Poll every 5 seconds
      return () => clearInterval(interval)
    }
  }, [syncStatus?.status, syncTimedOut])

  // Check for 60 second timeout on pending sync
  useEffect(() => {
    if (syncStartTime && !syncTimedOut) {
      const timeout = setTimeout(() => {
        setSyncTimedOut(true)
      }, 60000) // 60 seconds

      return () => clearTimeout(timeout)
    }
  }, [syncStartTime, syncTimedOut])

  // Handle search
  const handleSearch = () => {
    fetchModels(1)
  }

  // Handle page change
  const handlePageChange = (page: number) => {
    fetchModels(page)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Handle model click - fetch and display model detail
  const handleModelClick = async (modelId: string) => {
    setLoadingDetail(true)
    setSelectedModelDetail(null)
    setSearchQuery(modelId)
    setCurrentPage(1)

    try {
      const detail = await modelMarketClient.getModelDetail(modelId)
      setSelectedModelDetail(detail)

      // Search for this model to show it in the list
      await fetchModels(1)
    } catch (error) {
      console.error('Failed to fetch model detail:', error)
    } finally {
      setLoadingDetail(false)
    }

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Handle category toggle
  const handleCategoryToggle = (category: string) => {
    const newCategories = selectedCategories.includes(category)
      ? selectedCategories.filter(c => c !== category)
      : [...selectedCategories, category]
    setSelectedCategories(newCategories)
  }

  // Apply categories and refetch
  const applyCategories = () => {
    fetchModels(1)
    setCategoryDropdownOpen(false)
  }

  // Handle sync trigger
  const handleSync = async (syncType: 'full' | 'incremental') => {
    setSyncing(true)
    setSyncMessage(null)
    try {
      await modelMarketClient.triggerSync({ sync_type: syncType, source: 'huggingface' })
      await fetchFilterOptions()
      setSyncMessage({ type: 'success', text: `${syncType === 'full' ? '全量' : '增量'}同步已启动` })
      // Auto-clear success message after 3 seconds
      setTimeout(() => setSyncMessage(null), 3000)
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : '同步触发失败'
      setSyncMessage({ type: 'error', text: errorMsg })
      // Auto-clear error message after 5 seconds
      setTimeout(() => setSyncMessage(null), 5000)
    } finally {
      setSyncing(false)
    }
  }

  // Handle save AI config
  const handleSaveAiConfig = async () => {
    if (!aiModelName.trim() || !aiEndpointUrl.trim()) {
      setAiMessage({ type: 'error', text: '请填写模型名称和 API 地址' })
      setTimeout(() => setAiMessage(null), 3000)
      return
    }

    setAiSaving(true)
    setAiMessage(null)
    try {
      const config = await modelMarketClient.updateAIConfig({
        provider: aiProvider,
        model_name: aiModelName.trim(),
        endpoint_url: aiEndpointUrl.trim(),
        api_key: aiApiKey.trim() || null,
      })
      setAiConfig(config)
      setAiMessage({ type: 'success', text: 'AI 配置已保存' })
      setTimeout(() => setAiMessage(null), 3000)
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : '保存失败'
      setAiMessage({ type: 'error', text: errorMsg })
      setTimeout(() => setAiMessage(null), 5000)
    } finally {
      setAiSaving(false)
    }
  }

  // Sort options
  const sortOptions: Array<{ value: SortBy; label: string }> = [
    { value: 'last_modified', label: '最近更新' },
    { value: 'downloads', label: '下载量' },
    { value: 'likes', label: '点赞数' },
    { value: 'model_name', label: '模型名称' },
    { value: 'author', label: '作者' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">模型市场</h1>
        <p className="text-stone-600 dark:text-stone-400">
          模型数量：{total.toLocaleString()}
        </p>
      </div>

      {/* Top Bar - Search, Sort, Category, Config */}
      <div className="flex items-center gap-3">
        {/* Search Bar */}
        <div className="flex-1 flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="搜索模型名称、描述或作者..."
            className="flex-1 px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-6 py-2 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed"
          >
            搜索
          </button>
        </div>

        {/* Sync Progress Indicator - Auto-updates via polling */}
        <button
          disabled
          className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 flex items-center gap-2 cursor-default"
        >
          {syncTimedOut ? (
            // Timeout - no spinner, just show count
            <>
              <svg className="w-4 h-4 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="whitespace-nowrap">{syncStatus?.synced_models?.toLocaleString() || 0}</span>
            </>
          ) : (syncStatus?.status === 'running' || syncStatus?.status === 'pending') ? (
            <>
              <div className="w-4 h-4 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" />
              <span className="whitespace-nowrap">{syncStatus.synced_models?.toLocaleString() || 0} / {syncStatus.total_models?.toLocaleString() || '?'}</span>
            </>
          ) : syncStatus?.status === 'completed' ? (
            <>
              <svg className="w-4 h-4 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="whitespace-nowrap">{syncStatus.synced_models?.toLocaleString() || 0}</span>
            </>
          ) : syncStatus?.status === 'failed' ? (
            <>
              <svg className="w-4 h-4 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="whitespace-nowrap">失败</span>
            </>
          ) : (
            <>
              <svg className="w-4 h-4 text-stone-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <span className="whitespace-nowrap">{syncStatus?.synced_models?.toLocaleString() || 0}</span>
            </>
          )}
        </button>

        {/* Sort */}
        <div ref={sortDropdownRef} className="relative">
          <button
            onClick={() => setSortDropdownOpen(!sortDropdownOpen)}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center gap-2"
          >
            排序
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {sortDropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10">
              {sortOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => {
                    setSortBy(option.value)
                    setSortDropdownOpen(false)
                    fetchModels(1)
                  }}
                  className={`w-full px-4 py-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors ${
                    sortBy === option.value ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-700 dark:text-stone-300'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Category */}
        <div ref={categoryDropdownRef} className="relative">
          <button
            onClick={() => setCategoryDropdownOpen(!categoryDropdownOpen)}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center gap-2"
          >
            分类
            {selectedCategories.length > 0 && (
              <span className="px-2 py-0.5 text-xs bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded-full">
                {selectedCategories.length}
              </span>
            )}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {categoryDropdownOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10">
              <div className="p-3 max-h-64 overflow-y-auto">
                {categories.length > 0 ? (
                  categories.map((cat) => (
                    <button
                      key={cat.category}
                      onClick={() => handleCategoryToggle(cat.category)}
                      className={`w-full px-3 py-2 text-left text-sm rounded-lg transition-colors flex items-center justify-between ${
                        selectedCategories.includes(cat.category)
                          ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300'
                          : 'text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-700'
                      }`}
                    >
                      <span>{cat.category}</span>
                      <span className="text-xs text-stone-400">({cat.count})</span>
                    </button>
                  ))
                ) : (
                  <p className="text-sm text-stone-500 dark:text-stone-400 text-center py-4">
                    暂无分类
                  </p>
                )}
              </div>
              <div className="border-t border-stone-200 dark:border-stone-700 p-3 flex gap-2">
                <button
                  onClick={() => {
                    setSelectedCategories([])
                    fetchModels(1)
                    setCategoryDropdownOpen(false)
                  }}
                  className="flex-1 px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors"
                >
                  清空
                </button>
                <button
                  onClick={applyCategories}
                  className="flex-1 px-3 py-1.5 text-sm bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors"
                >
                  应用
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Config */}
        <div ref={configDropdownRef} className="relative">
          <button
            onClick={() => setConfigDropdownOpen(!configDropdownOpen)}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            配置
          </button>
          {configDropdownOpen && (
            <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-10">
              <div className="p-3 space-y-3">
                {/* Sync Section */}
                <div>
                  <h4 className="text-xs font-medium text-stone-900 dark:text-stone-100 mb-2">数据同步</h4>
                  <div className="space-y-1.5">
                    <button
                      onClick={() => handleSync('incremental')}
                      disabled={syncing || syncStatus?.status === 'running' || syncStatus?.status === 'pending'}
                      className="w-full px-2 py-1 text-xs border border-stone-300 dark:border-stone-600 rounded hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-center flex items-center justify-center gap-2"
                    >
                      <span>增量同步</span>
                      {(syncStatus?.status === 'running' || syncStatus?.status === 'pending') && (
                        <div className="w-3 h-3 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" />
                      )}
                    </button>
                    <button
                      onClick={() => handleSync('full')}
                      disabled={syncing || syncStatus?.status === 'running' || syncStatus?.status === 'pending'}
                      className="w-full px-2 py-1 text-xs border border-stone-300 dark:border-stone-600 rounded hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-center"
                    >
                      全量同步
                    </button>
                  </div>

                  {/* Sync Status Message */}
                  {syncMessage && (
                    <div className={`mt-2 px-2 py-1.5 text-[10px] rounded-md ${
                      syncMessage.type === 'success'
                        ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                        : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                    }`}>
                      {syncMessage.text}
                    </div>
                  )}

                  {syncStatus && !syncMessage && (
                    <div className="mt-1.5 text-[10px] text-stone-500 dark:text-stone-400">
                      状态：{syncStatus.status === 'completed' ? '已完成' : syncStatus.status === 'running' ? '同步中' : syncStatus.status === 'pending' ? '等待中' : syncStatus.status === 'failed' ? '失败' : '已取消'}
                      {syncStatus.synced_models > 0 && (
                        <span className="ml-1">({syncStatus.synced_models.toLocaleString()})</span>
                      )}
                    </div>
                  )}
                </div>

                {/* AI Recommend Config Section */}
                <div className="border-t border-stone-200 dark:border-stone-700 pt-3">
                  <h4 className="text-xs font-medium text-stone-900 dark:text-stone-100 mb-2">AI 推荐</h4>
                  <div className="space-y-2">
                    <select
                      value={aiProvider}
                      onChange={(e) => setAiProvider(e.target.value)}
                      className="w-full px-2 py-1 text-xs border border-stone-300 dark:border-stone-600 rounded bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-1 focus:ring-teal-500"
                    >
                      <option value="openai">OpenAI</option>
                      <option value="anthropic">Anthropic</option>
                      <option value="openai-compatible">OpenAI 兼容</option>
                    </select>
                    <input
                      type="text"
                      value={aiModelName}
                      onChange={(e) => setAiModelName(e.target.value)}
                      placeholder="模型名称 (如 gpt-4, claude-3-opus)"
                      className="w-full px-2 py-1 text-xs border border-stone-300 dark:border-stone-600 rounded bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-1 focus:ring-teal-500 focus:border-transparent"
                    />
                    <input
                      type="text"
                      value={aiEndpointUrl}
                      onChange={(e) => setAiEndpointUrl(e.target.value)}
                      placeholder="API 地址 (如 https://api.openai.com/v1)"
                      className="w-full px-2 py-1 text-xs border border-stone-300 dark:border-stone-600 rounded bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-1 focus:ring-teal-500 focus:border-transparent"
                    />
                    <input
                      type="password"
                      value={aiApiKey}
                      onChange={(e) => setAiApiKey(e.target.value)}
                      placeholder="API Key (可选)"
                      className="w-full px-2 py-1 text-xs border border-stone-300 dark:border-stone-600 rounded bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-1 focus:ring-teal-500 focus:border-transparent"
                    />
                    <button
                      onClick={handleSaveAiConfig}
                      disabled={aiSaving}
                      className="w-full px-2 py-1.5 text-xs bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded transition-colors disabled:cursor-not-allowed flex items-center justify-center gap-1"
                    >
                      {aiSaving ? (
                        <>
                          <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          保存中...
                        </>
                      ) : (
                        <>
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                          保存配置
                        </>
                      )}
                    </button>

                    {/* AI Config Message */}
                    {aiMessage && (
                      <div className={`px-2 py-1.5 text-[10px] rounded-md ${
                        aiMessage.type === 'success'
                          ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                          : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                      }`}>
                        {aiMessage.text}
                      </div>
                    )}

                    {aiConfig && !aiMessage && (
                      <div className="text-[10px] text-stone-500 dark:text-stone-400">
                        已配置: {aiConfig.provider}/{aiConfig.model_name}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Selected Model Detail */}
      {selectedModelDetail && (
        <div className="bg-gradient-to-r from-teal-50 to-emerald-50 dark:from-stone-800 dark:to-stone-700 rounded-xl p-6 border border-teal-200 dark:border-stone-600">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <h2 className="text-xl font-bold text-stone-900 dark:text-stone-100">
                  {selectedModelDetail.model_name}
                </h2>
                <span className="px-2 py-0.5 text-xs bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded-full">
                  {selectedModelDetail.pipeline_tag || 'N/A'}
                </span>
              </div>

              {selectedModelDetail.author && (
                <p className="text-sm text-stone-600 dark:text-stone-400 mb-2">
                  作者: <span className="font-medium">{selectedModelDetail.author}</span>
                </p>
              )}

              {selectedModelDetail.description && (
                <p className="text-sm text-stone-700 dark:text-stone-300 mb-3 line-clamp-2">
                  {selectedModelDetail.description}
                </p>
              )}

              <div className="flex flex-wrap gap-4 text-xs text-stone-500 dark:text-stone-400">
                <span>下载: {selectedModelDetail.downloads.toLocaleString()}</span>
                <span>点赞: {selectedModelDetail.likes.toLocaleString()}</span>
                <span>更新: {new Date(selectedModelDetail.last_modified).toLocaleDateString()}</span>
              </div>
            </div>

            <div className="flex gap-2 ml-4">
              <a
                href={selectedModelDetail.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 text-sm bg-stone-100 hover:bg-stone-200 dark:bg-stone-700 dark:hover:bg-stone-600 text-stone-700 dark:text-stone-300 rounded-lg transition-colors flex items-center gap-1"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                源码
              </a>
              <button
                onClick={() => {/* TODO: Handle deploy */}}
                className="px-4 py-2 text-sm bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors flex items-center gap-1"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                部署
              </button>
              <button
                onClick={() => setSelectedModelDetail(null)}
                className="p-2 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 transition-colors"
                title="关闭"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading detail indicator */}
      {loadingDetail && (
        <div className="flex items-center justify-center h-32">
          <div className="text-center">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-teal-600 mx-auto"></div>
            <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">加载模型详情...</p>
          </div>
        </div>
      )}

      {/* Model Grid */}
      {initialLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600 mx-auto"></div>
            <p className="mt-2 text-stone-600 dark:text-stone-400">加载中...</p>
          </div>
        </div>
      ) : models.length > 0 ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
            {models.map((model) => (
              <ModelCardComponent
                key={model.model_id}
                model={model}
                onClick={handleModelClick}
              />
            ))}
          </div>

          {/* Pagination - Bottom Left */}
          <div className="flex justify-start">
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={20}
              total={total}
              onPageChange={handlePageChange}
              loading={loading}
            />
          </div>
        </>
      ) : (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <svg className="w-16 h-16 text-stone-300 dark:text-stone-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">没有找到模型</h3>
            <p className="text-stone-600 dark:text-stone-400">
              {searchQuery || selectedCategories.length > 0
                ? '尝试调整搜索条件或分类筛选'
                : '暂无模型数据，请点击配置按钮触发同步'}
            </p>
          </div>
        </div>
      )}

      {/* AI Recommend Chat */}
      <AIRecommendChat onModelSelect={handleModelClick} />
    </div>
  )
}
