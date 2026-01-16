/**
 * Rerank Tab Component
 *
 * Test document reranking with different models.
 */

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { List, Play, Loader2, Plus, X, AlertCircle, ArrowUp, ArrowDown } from 'lucide-react'
import { playgroundClient, RerankResponse } from '../api/playgroundClient'
import { chatClient } from '../../chat/api/chatClient'

export function RerankTab() {
  const [query, setQuery] = useState('')
  const [documents, setDocuments] = useState<string[]>(['', ''])
  const [topN, setTopN] = useState<number>(10)
  const [selectedProfileId, setSelectedProfileId] = useState<string>('')
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [result, setResult] = useState<RerankResponse | null>(null)

  // Get model profiles with rerank capability
  const { data: profiles } = useQuery({
    queryKey: ['model-profiles-rerank'],
    queryFn: () => chatClient.getModelProfiles('rerank'),
  })

  // Rerank mutation
  const rerankMutation = useMutation({
    mutationFn: () =>
      playgroundClient.rerank({
        query,
        documents: documents.filter(d => d.trim()),
        model: selectedModel,
        model_profile_id: selectedProfileId || undefined,
        top_n: topN,
      }),
    onSuccess: (data) => {
      setResult(data)
    },
  })

  const handleProfileChange = (profileId: string) => {
    setSelectedProfileId(profileId)
    const profile = profiles?.find(p => p.id === profileId)
    if (profile && profile.available_models.length > 0) {
      setSelectedModel(profile.available_models[0])
    }
  }

  const addDocument = () => {
    setDocuments([...documents, ''])
  }

  const removeDocument = (index: number) => {
    if (documents.length <= 2) return
    setDocuments(documents.filter((_, i) => i !== index))
  }

  const updateDocument = (index: number, value: string) => {
    const newDocs = [...documents]
    newDocs[index] = value
    setDocuments(newDocs)
  }

  const validDocuments = documents.filter(d => d.trim())
  const canSubmit = query.trim() && validDocuments.length >= 2 && selectedModel

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-stone-200 dark:border-stone-700">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
            <List className="w-5 h-5 text-orange-600 dark:text-orange-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
              Rerank
            </h2>
            <p className="text-sm text-stone-500 dark:text-stone-400">
              根据查询对文档列表进行相关性重排序
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Input Panel */}
        <div className="w-1/2 flex flex-col border-r border-stone-200 dark:border-stone-700">
          <div className="p-4 space-y-4 flex-1 overflow-y-auto">
            {/* Model Selection */}
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  模型配置
                </label>
                <select
                  value={selectedProfileId}
                  onChange={(e) => handleProfileChange(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                >
                  <option value="">选择配置...</option>
                  {profiles?.map(profile => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              </div>

              {selectedProfileId && (
                <div>
                  <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                    模型
                  </label>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                  >
                    {profiles
                      ?.find(p => p.id === selectedProfileId)
                      ?.available_models.map(model => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))}
                  </select>
                </div>
              )}
            </div>

            {/* Query */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                查询文本
              </label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="输入查询..."
                className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
              />
            </div>

            {/* Top N */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                返回数量 (Top N)
              </label>
              <input
                type="number"
                value={topN}
                onChange={(e) => setTopN(parseInt(e.target.value) || 10)}
                min={1}
                max={100}
                className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
              />
            </div>

            {/* Documents */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-stone-700 dark:text-stone-300">
                  文档列表 ({validDocuments.length} 个有效)
                </label>
                <button
                  onClick={addDocument}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-teal-600 hover:text-teal-700 hover:bg-teal-50 dark:hover:bg-teal-900/20 rounded transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  添加
                </button>
              </div>
              <div className="space-y-2">
                {documents.map((doc, index) => (
                  <div key={index} className="flex gap-2">
                    <div className="w-6 h-8 flex items-center justify-center text-xs text-stone-400">
                      {index + 1}.
                    </div>
                    <input
                      type="text"
                      value={doc}
                      onChange={(e) => updateDocument(index, e.target.value)}
                      placeholder={`文档 ${index + 1}...`}
                      className="flex-1 px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                    />
                    <button
                      onClick={() => removeDocument(index)}
                      disabled={documents.length <= 2}
                      className="p-2 hover:bg-stone-100 dark:hover:bg-stone-700 rounded-lg transition-colors disabled:opacity-30"
                    >
                      <X className="w-4 h-4 text-stone-500" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Submit Button */}
          <div className="p-4 border-t border-stone-200 dark:border-stone-700">
            <button
              onClick={() => rerankMutation.mutate()}
              disabled={!canSubmit || rerankMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed"
            >
              {rerankMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  重排序中...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  开始重排序
                </>
              )}
            </button>
          </div>
        </div>

        {/* Result Panel */}
        <div className="w-1/2 flex flex-col bg-stone-50 dark:bg-stone-900/50">
          <div className="px-4 py-3 border-b border-stone-200 dark:border-stone-700">
            <span className="text-sm font-medium text-stone-700 dark:text-stone-300">
              重排序结果
            </span>
          </div>

          <div className="flex-1 p-4 overflow-y-auto">
            {rerankMutation.error ? (
              <div className="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-red-700 dark:text-red-400">
                    重排序失败
                  </p>
                  <p className="text-sm text-red-600 dark:text-red-300 mt-1">
                    {(rerankMutation.error as any)?.response?.data?.detail ||
                      (rerankMutation.error as Error).message}
                  </p>
                </div>
              </div>
            ) : result ? (
              <div className="space-y-4">
                {/* Model Info */}
                <div className="p-3 bg-white dark:bg-stone-800 rounded-lg">
                  <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
                    使用模型
                  </div>
                  <div className="text-sm font-medium text-stone-900 dark:text-stone-100">
                    {result.model}
                  </div>
                </div>

                {/* Results */}
                <div>
                  <div className="text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                    排序结果
                  </div>
                  <div className="space-y-2">
                    {result.results.map((item, idx) => {
                      const originalIndex = item.index
                      const positionChange = originalIndex - idx

                      return (
                        <div
                          key={idx}
                          className="p-3 bg-white dark:bg-stone-800 rounded-lg"
                        >
                          <div className="flex items-start gap-3">
                            <div className="flex flex-col items-center">
                              <div className="w-6 h-6 rounded-full bg-teal-100 dark:bg-teal-900/30 flex items-center justify-center text-xs font-medium text-teal-600 dark:text-teal-400">
                                {idx + 1}
                              </div>
                              {positionChange !== 0 && (
                                <div className={`flex items-center text-xs mt-1 ${
                                  positionChange > 0
                                    ? 'text-green-600'
                                    : 'text-red-500'
                                }`}>
                                  {positionChange > 0 ? (
                                    <>
                                      <ArrowUp className="w-3 h-3" />
                                      {positionChange}
                                    </>
                                  ) : (
                                    <>
                                      <ArrowDown className="w-3 h-3" />
                                      {Math.abs(positionChange)}
                                    </>
                                  )}
                                </div>
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-stone-700 dark:text-stone-300">
                                {item.document}
                              </p>
                              <div className="flex items-center gap-4 mt-2 text-xs text-stone-500">
                                <span>
                                  原位置: {originalIndex + 1}
                                </span>
                                <span>
                                  相关性: {(item.relevance_score * 100).toFixed(2)}%
                                </span>
                              </div>
                            </div>
                            {/* Score Bar */}
                            <div className="w-20">
                              <div className="h-2 bg-stone-200 dark:bg-stone-700 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-teal-500 rounded-full"
                                  style={{ width: `${item.relevance_score * 100}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-stone-500 dark:text-stone-400">
                <div className="text-center">
                  <List className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">输入查询和文档后开始重排序</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
