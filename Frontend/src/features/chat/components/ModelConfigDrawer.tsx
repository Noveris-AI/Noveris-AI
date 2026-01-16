/**
 * Model Configuration Drawer
 *
 * Dark-themed drawer for creating/editing model profiles.
 */

import { useEffect, useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Eye, EyeOff, Loader2, ChevronDown } from 'lucide-react'
import { z } from 'zod'
import { chatClient, ModelProfile } from '../api/chatClient'

// Form validation schema
const modelConfigSchema = z.object({
  modelName: z.string().min(1, '请输入模型名称'),
  modelType: z.string().min(1, '请选择模型类型'),
  credentialName: z.string().optional(),
  displayName: z.string().optional(),
  apiKey: z.string().optional(),
  baseUrl: z
    .string()
    .min(1, '请输入 API endpoint URL')
    .refine(
      (val) => val.startsWith('http://') || val.startsWith('https://'),
      '必须以 http:// 或 https:// 开头'
    )
    .refine((val) => !val.includes(' '), '不允许包含空格'),
  endpointModel: z.string().optional(),
})

type ModelConfigFormValues = z.infer<typeof modelConfigSchema>

// Model type options
const MODEL_TYPES = [
  { value: 'llm', label: '大语言模型（LLM）' },
  { value: 'multimodal', label: '多模态（Multimodal）' },
  { value: 'embedding', label: 'Embedding（向量）' },
  { value: 'rerank', label: 'Rerank（重排）' },
  { value: 'image', label: 'Image（生图）' },
  { value: 'video', label: 'Video（生视频）' },
  { value: 'audio', label: 'Audio（音频）' },
  { value: 'speech', label: 'Speech（语音/ASR/TTS）' },
  { value: 'moderation', label: 'Moderation（内容安全）' },
  { value: 'custom', label: 'Custom（自定义）' },
]

// Map model type to capabilities
const TYPE_TO_CAPABILITIES: Record<string, string[]> = {
  llm: ['chat'],
  multimodal: ['chat', 'vision'],
  embedding: ['embedding'],
  rerank: ['rerank'],
  image: ['image'],
  video: ['video'],
  audio: ['audio'],
  speech: ['speech', 'tts', 'asr'],
  moderation: ['moderation'],
  custom: ['chat'],
}

interface ModelConfigDrawerProps {
  isOpen: boolean
  onClose: () => void
  editingProfile?: ModelProfile | null
}

export function ModelConfigDrawer({
  isOpen,
  onClose,
  editingProfile,
}: ModelConfigDrawerProps) {
  const [showApiKey, setShowApiKey] = useState(false)
  const [resetApiKey, setResetApiKey] = useState(false)
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ModelConfigFormValues>({
    resolver: zodResolver(modelConfigSchema),
    defaultValues: {
      modelName: '',
      modelType: '',
      credentialName: '',
      displayName: '',
      apiKey: '',
      baseUrl: '',
      endpointModel: '',
    },
  })

  // Load editing profile data
  useEffect(() => {
    if (editingProfile) {
      // Map backend fields to form fields
      const modelType = detectModelType(editingProfile.capabilities)
      reset({
        modelName: editingProfile.name,
        modelType,
        credentialName: editingProfile.description || '',
        displayName: editingProfile.name,
        apiKey: '', // Never show actual API key
        baseUrl: editingProfile.base_url,
        endpointModel: editingProfile.default_model || '',
      })
      setResetApiKey(false)
    } else {
      reset({
        modelName: '',
        modelType: '',
        credentialName: '',
        displayName: '',
        apiKey: '',
        baseUrl: '',
        endpointModel: '',
      })
    }
  }, [editingProfile, reset])

  // Detect model type from capabilities
  function detectModelType(capabilities: string[]): string {
    if (capabilities.includes('embedding')) return 'embedding'
    if (capabilities.includes('rerank')) return 'rerank'
    if (capabilities.includes('image')) return 'image'
    if (capabilities.includes('video')) return 'video'
    if (capabilities.includes('audio')) return 'audio'
    if (capabilities.includes('speech') || capabilities.includes('tts')) return 'speech'
    if (capabilities.includes('moderation')) return 'moderation'
    if (capabilities.includes('vision')) return 'multimodal'
    return 'llm'
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: Partial<ModelProfile> & { api_key?: string }) =>
      chatClient.createModelProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['model-profiles'] })
      onClose()
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: Partial<ModelProfile> & { api_key?: string }
    }) => chatClient.updateModelProfile(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['model-profiles'] })
      onClose()
    },
  })

  const onSubmit = async (values: ModelConfigFormValues) => {
    // Normalize baseUrl (remove trailing slash)
    let normalizedUrl = values.baseUrl.trim()
    if (normalizedUrl.endsWith('/')) {
      normalizedUrl = normalizedUrl.slice(0, -1)
    }

    // Map form fields to backend fields
    const capabilities = TYPE_TO_CAPABILITIES[values.modelType] || ['chat']
    const availableModels = values.endpointModel
      ? [values.endpointModel]
      : ['default']

    const payload: Partial<ModelProfile> & { api_key?: string } = {
      name: values.displayName?.trim() || values.modelName,
      description: values.credentialName?.trim() || undefined,
      base_url: normalizedUrl,
      default_model: values.endpointModel || 'default',
      available_models: availableModels,
      capabilities,
      enabled: true,
    }

    // Only include API key if provided or reset
    if (values.apiKey?.trim()) {
      payload.api_key = values.apiKey.trim()
    }

    if (editingProfile) {
      updateMutation.mutate({ id: editingProfile.id, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 z-50 h-full w-[600px] max-w-full bg-[#141414] shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/5">
          <h2 className="text-lg font-semibold text-white">
            {editingProfile ? '编辑模型配置' : '新增模型配置'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/5 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-stone-400" />
          </button>
        </div>

        {/* Form Content */}
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="flex-1 overflow-y-auto"
        >
          <div className="px-6 py-6 space-y-5">
            {/* Error Message */}
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400">
                {(error as any)?.response?.data?.detail || (error as Error).message}
              </div>
            )}

            {/* Model Name */}
            <div className="space-y-2">
              <label className="block text-sm text-stone-300">
                模型名称 <span className="text-red-500">*</span>
              </label>
              <input
                {...register('modelName')}
                placeholder="输入模型全称"
                className="w-full px-4 py-3 bg-[#1c1c1c] border border-white/5 rounded-xl text-white placeholder-stone-500 focus:outline-none focus:border-white/20 transition-colors"
              />
              {errors.modelName && (
                <p className="text-xs text-red-400 mt-1">
                  {errors.modelName.message}
                </p>
              )}
            </div>

            {/* Model Type */}
            <div className="space-y-2">
              <label className="block text-sm text-stone-300">
                模型类型 <span className="text-red-500">*</span>
              </label>
              <Controller
                name="modelType"
                control={control}
                render={({ field }) => (
                  <div className="relative">
                    <select
                      {...field}
                      className="w-full px-4 py-3 bg-[#1c1c1c] border border-white/5 rounded-xl text-white appearance-none focus:outline-none focus:border-white/20 transition-colors cursor-pointer"
                    >
                      <option value="" className="bg-[#1c1c1c] text-stone-500">
                        请选择
                      </option>
                      {MODEL_TYPES.map((type) => (
                        <option
                          key={type.value}
                          value={type.value}
                          className="bg-[#1c1c1c]"
                        >
                          {type.label}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-500 pointer-events-none" />
                  </div>
                )}
              />
              {errors.modelType && (
                <p className="text-xs text-red-400 mt-1">
                  {errors.modelType.message}
                </p>
              )}
            </div>

            {/* Divider - Model Credentials */}
            <div className="flex items-center gap-3 pt-4">
              <div className="flex-1 h-px bg-white/5"></div>
              <span className="text-xs text-stone-500 uppercase tracking-wider">
                模型凭据
              </span>
              <div className="flex-1 h-px bg-white/5"></div>
            </div>

            {/* Credential Name */}
            <div className="space-y-2">
              <label className="block text-sm text-stone-300">凭据名称</label>
              <input
                {...register('credentialName')}
                placeholder="请输入"
                className="w-full px-4 py-3 bg-[#1c1c1c] border border-white/5 rounded-xl text-white placeholder-stone-500 focus:outline-none focus:border-white/20 transition-colors"
              />
            </div>

            {/* Display Name */}
            <div className="space-y-2">
              <label className="block text-sm text-stone-300">
                模型显示名称
              </label>
              <input
                {...register('displayName')}
                placeholder="模型在界面的显示名称"
                className="w-full px-4 py-3 bg-[#1c1c1c] border border-white/5 rounded-xl text-white placeholder-stone-500 focus:outline-none focus:border-white/20 transition-colors"
              />
            </div>

            {/* API Key */}
            <div className="space-y-2">
              <label className="block text-sm text-stone-300">API Key</label>
              <div className="relative">
                {editingProfile?.has_api_key && !resetApiKey ? (
                  <div className="flex items-center gap-3">
                    <div className="flex-1 px-4 py-3 bg-[#1c1c1c] border border-white/5 rounded-xl text-stone-500">
                      ••••••••••••••••
                    </div>
                    <button
                      type="button"
                      onClick={() => setResetApiKey(true)}
                      className="px-4 py-3 bg-white/5 hover:bg-white/10 border border-white/5 rounded-xl text-sm text-stone-300 transition-colors whitespace-nowrap"
                    >
                      重新输入
                    </button>
                  </div>
                ) : (
                  <>
                    <input
                      {...register('apiKey')}
                      type={showApiKey ? 'text' : 'password'}
                      placeholder="在此输入您的 API Key"
                      className="w-full px-4 py-3 pr-12 bg-[#1c1c1c] border border-white/5 rounded-xl text-white placeholder-stone-500 focus:outline-none focus:border-white/20 transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 text-stone-500 hover:text-stone-300 transition-colors"
                    >
                      {showApiKey ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Divider - Endpoint Info */}
            <div className="flex items-center gap-3 pt-4">
              <div className="flex-1 h-px bg-white/5"></div>
              <span className="text-xs text-stone-500 uppercase tracking-wider">
                Endpoint 信息
              </span>
              <div className="flex-1 h-px bg-white/5"></div>
            </div>

            {/* API Endpoint URL */}
            <div className="space-y-2">
              <label className="block text-sm text-stone-300">
                API endpoint URL <span className="text-red-500">*</span>
              </label>
              <input
                {...register('baseUrl')}
                placeholder="Base URL, e.g. https://api.openai.com/v1"
                className="w-full px-4 py-3 bg-[#1c1c1c] border border-white/5 rounded-xl text-white placeholder-stone-500 focus:outline-none focus:border-white/20 transition-colors"
              />
              {errors.baseUrl && (
                <p className="text-xs text-red-400 mt-1">
                  {errors.baseUrl.message}
                </p>
              )}
            </div>

            {/* Endpoint Model Name */}
            <div className="space-y-2">
              <label className="block text-sm text-stone-300">
                API endpoint中的模型名称
              </label>
              <input
                {...register('endpointModel')}
                placeholder="endpoint model name, e.g. chatgpt4.0"
                className="w-full px-4 py-3 bg-[#1c1c1c] border border-white/5 rounded-xl text-white placeholder-stone-500 focus:outline-none focus:border-white/20 transition-colors"
              />
            </div>
          </div>
        </form>

        {/* Footer Actions - Sticky */}
        <div className="px-6 py-4 border-t border-white/5 bg-[#141414] flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="px-6 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm text-stone-300 font-medium transition-colors disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="submit"
            onClick={handleSubmit(onSubmit)}
            disabled={isPending}
            className="px-6 py-2.5 bg-teal-600 hover:bg-teal-500 rounded-xl text-sm text-white font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            保存
          </button>
        </div>
      </div>
    </>
  )
}
