/**
 * Images Tab Component
 *
 * Test image generation with different models.
 */

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Image, Play, Loader2, Download, AlertCircle, Maximize2 } from 'lucide-react'
import { playgroundClient, ImageGenerationResponse } from '../api/playgroundClient'
import { chatClient } from '../../chat/api/chatClient'

const IMAGE_SIZES = ['256x256', '512x512', '1024x1024', '1024x1792', '1792x1024']
const IMAGE_QUALITIES = ['standard', 'hd']
const IMAGE_STYLES = ['vivid', 'natural']

export function ImagesTab() {
  const [prompt, setPrompt] = useState('')
  const [size, setSize] = useState('1024x1024')
  const [quality, setQuality] = useState('standard')
  const [style, setStyle] = useState('vivid')
  const [count, setCount] = useState(1)
  const [selectedProfileId, setSelectedProfileId] = useState<string>('')
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [result, setResult] = useState<ImageGenerationResponse | null>(null)
  const [previewImage, setPreviewImage] = useState<string | null>(null)

  // Get model profiles with image capability
  const { data: profiles } = useQuery({
    queryKey: ['model-profiles-image'],
    queryFn: () => chatClient.getModelProfiles('image'),
  })

  // Image generation mutation
  const imageMutation = useMutation({
    mutationFn: () =>
      playgroundClient.generateImage({
        prompt,
        model: selectedModel,
        model_profile_id: selectedProfileId || undefined,
        n: count,
        size,
        quality,
        style,
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

  const handleDownload = async (url: string, index: number) => {
    const response = await fetch(url)
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = `generated-image-${index + 1}.png`
    a.click()
    URL.revokeObjectURL(objectUrl)
  }

  const canSubmit = prompt.trim() && selectedModel

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-stone-200 dark:border-stone-700">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-pink-100 dark:bg-pink-900/30 flex items-center justify-center">
            <Image className="w-5 h-5 text-pink-600 dark:text-pink-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
              Image Generation
            </h2>
            <p className="text-sm text-stone-500 dark:text-stone-400">
              根据文字描述生成图像
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

            {/* Prompt */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                图像描述
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="描述你想要生成的图像..."
                rows={4}
                className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 resize-none"
              />
            </div>

            {/* Settings */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  尺寸
                </label>
                <select
                  value={size}
                  onChange={(e) => setSize(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                >
                  {IMAGE_SIZES.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  数量
                </label>
                <select
                  value={count}
                  onChange={(e) => setCount(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                >
                  {[1, 2, 3, 4].map(n => (
                    <option key={n} value={n}>{n} 张</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  质量
                </label>
                <select
                  value={quality}
                  onChange={(e) => setQuality(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                >
                  {IMAGE_QUALITIES.map(q => (
                    <option key={q} value={q}>{q === 'hd' ? 'HD 高清' : '标准'}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  风格
                </label>
                <select
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                >
                  {IMAGE_STYLES.map(s => (
                    <option key={s} value={s}>{s === 'vivid' ? '鲜艳' : '自然'}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Submit Button */}
          <div className="p-4 border-t border-stone-200 dark:border-stone-700">
            <button
              onClick={() => imageMutation.mutate()}
              disabled={!canSubmit || imageMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed"
            >
              {imageMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  生成图像
                </>
              )}
            </button>
          </div>
        </div>

        {/* Result Panel */}
        <div className="w-1/2 flex flex-col bg-stone-50 dark:bg-stone-900/50">
          <div className="px-4 py-3 border-b border-stone-200 dark:border-stone-700">
            <span className="text-sm font-medium text-stone-700 dark:text-stone-300">
              生成结果
            </span>
          </div>

          <div className="flex-1 p-4 overflow-y-auto">
            {imageMutation.error ? (
              <div className="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-red-700 dark:text-red-400">
                    生成失败
                  </p>
                  <p className="text-sm text-red-600 dark:text-red-300 mt-1">
                    {(imageMutation.error as any)?.response?.data?.detail ||
                      (imageMutation.error as Error).message}
                  </p>
                </div>
              </div>
            ) : result ? (
              <div className="space-y-4">
                {/* Images Grid */}
                <div className={`grid gap-4 ${result.data.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
                  {result.data.map((image, index) => {
                    const imageUrl = image.url || (image.b64_json ? `data:image/png;base64,${image.b64_json}` : '')

                    return (
                      <div
                        key={index}
                        className="relative group rounded-lg overflow-hidden bg-white dark:bg-stone-800"
                      >
                        <img
                          src={imageUrl}
                          alt={`Generated ${index + 1}`}
                          className="w-full aspect-square object-cover"
                        />
                        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                          <button
                            onClick={() => setPreviewImage(imageUrl)}
                            className="p-2 bg-white/20 hover:bg-white/30 rounded-lg backdrop-blur-sm"
                          >
                            <Maximize2 className="w-5 h-5 text-white" />
                          </button>
                          {image.url && (
                            <button
                              onClick={() => handleDownload(image.url!, index)}
                              className="p-2 bg-white/20 hover:bg-white/30 rounded-lg backdrop-blur-sm"
                            >
                              <Download className="w-5 h-5 text-white" />
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>

                {/* Revised Prompts */}
                {result.data.some(d => d.revised_prompt) && (
                  <div>
                    <div className="text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                      优化后的描述
                    </div>
                    {result.data.map((image, index) =>
                      image.revised_prompt ? (
                        <div
                          key={index}
                          className="p-3 bg-white dark:bg-stone-800 rounded-lg text-sm text-stone-600 dark:text-stone-400 mb-2"
                        >
                          {image.revised_prompt}
                        </div>
                      ) : null
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-stone-500 dark:text-stone-400">
                <div className="text-center">
                  <Image className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">输入描述并点击生成</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Image Preview Modal */}
      {previewImage && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-8"
          onClick={() => setPreviewImage(null)}
        >
          <img
            src={previewImage}
            alt="Preview"
            className="max-w-full max-h-full object-contain rounded-lg"
          />
        </div>
      )}
    </div>
  )
}
