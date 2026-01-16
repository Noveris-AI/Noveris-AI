/**
 * Embeddings Tab Component
 *
 * Test embedding generation with different models.
 */

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Code, Play, Loader2, Copy, Check, AlertCircle } from 'lucide-react'
import { playgroundClient, EmbeddingResponse } from '../api/playgroundClient'
import { chatClient } from '../../chat/api/chatClient'

export function EmbeddingsTab() {
  const [input, setInput] = useState('')
  const [selectedProfileId, setSelectedProfileId] = useState<string>('')
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [result, setResult] = useState<EmbeddingResponse | null>(null)
  const [copied, setCopied] = useState(false)

  // Get model profiles with embedding capability
  const { data: profiles } = useQuery({
    queryKey: ['model-profiles-embeddings'],
    queryFn: () => chatClient.getModelProfiles('embedding'),
  })

  // Embedding mutation
  const embeddingMutation = useMutation({
    mutationFn: () =>
      playgroundClient.createEmbedding({
        input,
        model: selectedModel,
        model_profile_id: selectedProfileId || undefined,
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

  const handleCopy = async () => {
    if (!result) return
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const canSubmit = input.trim() && selectedModel

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-stone-200 dark:border-stone-700">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
            <Code className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
              Embeddings
            </h2>
            <p className="text-sm text-stone-500 dark:text-stone-400">
              将文本转换为向量表示，用于语义搜索和相似度计算
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

            {/* Input Text */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                输入文本
              </label>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="输入要转换为向量的文本..."
                rows={8}
                className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 resize-none"
              />
            </div>
          </div>

          {/* Submit Button */}
          <div className="p-4 border-t border-stone-200 dark:border-stone-700">
            <button
              onClick={() => embeddingMutation.mutate()}
              disabled={!canSubmit || embeddingMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed"
            >
              {embeddingMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  生成 Embedding
                </>
              )}
            </button>
          </div>
        </div>

        {/* Result Panel */}
        <div className="w-1/2 flex flex-col bg-stone-50 dark:bg-stone-900/50">
          <div className="px-4 py-3 border-b border-stone-200 dark:border-stone-700 flex items-center justify-between">
            <span className="text-sm font-medium text-stone-700 dark:text-stone-300">
              结果
            </span>
            {result && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 px-2 py-1 text-xs text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 hover:bg-stone-200 dark:hover:bg-stone-700 rounded transition-colors"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    已复制
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    复制
                  </>
                )}
              </button>
            )}
          </div>

          <div className="flex-1 p-4 overflow-y-auto">
            {embeddingMutation.error ? (
              <div className="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-red-700 dark:text-red-400">
                    生成失败
                  </p>
                  <p className="text-sm text-red-600 dark:text-red-300 mt-1">
                    {(embeddingMutation.error as any)?.response?.data?.detail ||
                      (embeddingMutation.error as Error).message}
                  </p>
                </div>
              </div>
            ) : result ? (
              <div className="space-y-4">
                {/* Summary */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-white dark:bg-stone-800 rounded-lg">
                    <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
                      模型
                    </div>
                    <div className="text-sm font-medium text-stone-900 dark:text-stone-100">
                      {result.model}
                    </div>
                  </div>
                  <div className="p-3 bg-white dark:bg-stone-800 rounded-lg">
                    <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
                      维度
                    </div>
                    <div className="text-sm font-medium text-stone-900 dark:text-stone-100">
                      {result.data[0]?.embedding.length || 0}
                    </div>
                  </div>
                  <div className="p-3 bg-white dark:bg-stone-800 rounded-lg">
                    <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
                      Prompt Tokens
                    </div>
                    <div className="text-sm font-medium text-stone-900 dark:text-stone-100">
                      {result.usage.prompt_tokens}
                    </div>
                  </div>
                  <div className="p-3 bg-white dark:bg-stone-800 rounded-lg">
                    <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
                      Total Tokens
                    </div>
                    <div className="text-sm font-medium text-stone-900 dark:text-stone-100">
                      {result.usage.total_tokens}
                    </div>
                  </div>
                </div>

                {/* Vector Preview */}
                <div>
                  <div className="text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                    向量预览 (前20维)
                  </div>
                  <div className="p-3 bg-white dark:bg-stone-800 rounded-lg">
                    <code className="text-xs text-stone-600 dark:text-stone-400 break-all">
                      [{result.data[0]?.embedding.slice(0, 20).map(v => v.toFixed(6)).join(', ')}...]
                    </code>
                  </div>
                </div>

                {/* Full JSON */}
                <div>
                  <div className="text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                    完整响应
                  </div>
                  <pre className="p-3 bg-white dark:bg-stone-800 rounded-lg text-xs text-stone-600 dark:text-stone-400 overflow-x-auto max-h-64">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-stone-500 dark:text-stone-400">
                <div className="text-center">
                  <Code className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">输入文本并点击生成</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
