/**
 * Model Profile Settings Component
 *
 * Modal for managing model profiles (CRUD operations).
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  X,
  Plus,
  Edit2,
  Trash2,
  Check,
  AlertCircle,
  Eye,
  EyeOff,
  Loader2,
  Server,
  Cloud,
  Zap,
} from 'lucide-react'
import { chatClient, ModelProfile } from '../api/chatClient'

interface ModelProfileSettingsProps {
  profiles: ModelProfile[]
  onClose: () => void
  onRefresh: () => void
}

type FormMode = 'list' | 'create' | 'edit'

interface FormData {
  name: string
  description: string
  base_url: string
  api_key: string
  default_model: string
  available_models: string
  timeout_ms: number
  enabled: boolean
  is_default: boolean
}

const initialFormData: FormData = {
  name: '',
  description: '',
  base_url: '',
  api_key: '',
  default_model: '',
  available_models: '',
  timeout_ms: 60000,
  enabled: true,
  is_default: false,
}

export function ModelProfileSettings({
  profiles,
  onClose,
  onRefresh,
}: ModelProfileSettingsProps) {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<FormMode>('list')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formData, setFormData] = useState<FormData>(initialFormData)
  const [showApiKey, setShowApiKey] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: Partial<ModelProfile> & { api_key?: string }) =>
      chatClient.createModelProfile(data),
    onSuccess: () => {
      onRefresh()
      setMode('list')
      setFormData(initialFormData)
      setError(null)
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '创建失败')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ModelProfile> & { api_key?: string } }) =>
      chatClient.updateModelProfile(id, data),
    onSuccess: () => {
      onRefresh()
      setMode('list')
      setEditingId(null)
      setFormData(initialFormData)
      setError(null)
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '更新失败')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: chatClient.deleteModelProfile.bind(chatClient),
    onSuccess: () => {
      onRefresh()
    },
  })

  const handleCreate = () => {
    setMode('create')
    setFormData(initialFormData)
    setError(null)
  }

  const handleEdit = (profile: ModelProfile) => {
    setMode('edit')
    setEditingId(profile.id)
    setFormData({
      name: profile.name,
      description: profile.description || '',
      base_url: profile.base_url,
      api_key: '',
      default_model: profile.default_model,
      available_models: profile.available_models.join(', '),
      timeout_ms: profile.timeout_ms,
      enabled: profile.enabled,
      is_default: profile.is_default,
    })
    setError(null)
  }

  const handleDelete = (id: string) => {
    if (confirm('确定要删除此配置吗？此操作不可恢复。')) {
      deleteMutation.mutate(id)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const availableModels = formData.available_models
      .split(',')
      .map(m => m.trim())
      .filter(Boolean)

    if (availableModels.length === 0) {
      setError('请至少添加一个可用模型')
      return
    }

    const data: Partial<ModelProfile> & { api_key?: string } = {
      name: formData.name,
      description: formData.description || undefined,
      base_url: formData.base_url,
      default_model: formData.default_model || availableModels[0],
      available_models: availableModels,
      timeout_ms: formData.timeout_ms,
      enabled: formData.enabled,
      is_default: formData.is_default,
    }

    if (formData.api_key) {
      data.api_key = formData.api_key
    }

    if (mode === 'create') {
      createMutation.mutate(data)
    } else if (editingId) {
      updateMutation.mutate({ id: editingId, data })
    }
  }

  const getProfileIcon = (profile: ModelProfile) => {
    if (profile.name.toLowerCase().includes('gateway') || profile.name.toLowerCase().includes('内部')) {
      return Server
    }
    if (profile.name.toLowerCase().includes('openai')) {
      return Zap
    }
    return Cloud
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl max-h-[90vh] bg-white dark:bg-stone-800 rounded-xl shadow-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-stone-200 dark:border-stone-700">
          <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
            {mode === 'list' && '模型配置管理'}
            {mode === 'create' && '新建配置'}
            {mode === 'edit' && '编辑配置'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-stone-100 dark:hover:bg-stone-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-stone-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {mode === 'list' ? (
            <>
              {/* Profile List */}
              <div className="space-y-3">
                {profiles.length === 0 ? (
                  <div className="text-center py-8 text-stone-500 dark:text-stone-400">
                    <Cloud className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p>暂无模型配置</p>
                  </div>
                ) : (
                  profiles.map(profile => {
                    const Icon = getProfileIcon(profile)
                    return (
                      <div
                        key={profile.id}
                        className="flex items-center gap-4 p-4 bg-stone-50 dark:bg-stone-900/50 rounded-lg"
                      >
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          profile.enabled
                            ? 'bg-teal-100 dark:bg-teal-900/30'
                            : 'bg-stone-200 dark:bg-stone-700'
                        }`}>
                          <Icon className={`w-5 h-5 ${
                            profile.enabled
                              ? 'text-teal-600 dark:text-teal-400'
                              : 'text-stone-400'
                          }`} />
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="font-medium text-stone-900 dark:text-stone-100">
                              {profile.name}
                            </h3>
                            {profile.is_default && (
                              <span className="px-1.5 py-0.5 bg-teal-100 dark:bg-teal-900/30 text-teal-600 dark:text-teal-400 text-xs rounded">
                                默认
                              </span>
                            )}
                            {!profile.enabled && (
                              <span className="px-1.5 py-0.5 bg-stone-200 dark:bg-stone-700 text-stone-500 text-xs rounded">
                                已禁用
                              </span>
                            )}
                          </div>
                          <div className="text-sm text-stone-500 dark:text-stone-400 truncate">
                            {profile.base_url}
                          </div>
                          <div className="text-xs text-stone-400 dark:text-stone-500 mt-1">
                            {profile.available_models.length} 个模型 · {profile.has_api_key ? '已配置密钥' : '未配置密钥'}
                          </div>
                        </div>

                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleEdit(profile)}
                            className="p-2 hover:bg-stone-200 dark:hover:bg-stone-700 rounded-lg transition-colors"
                          >
                            <Edit2 className="w-4 h-4 text-stone-500" />
                          </button>
                          <button
                            onClick={() => handleDelete(profile.id)}
                            disabled={deleteMutation.isPending}
                            className="p-2 hover:bg-red-100 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </button>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>

              {/* Add Button */}
              <button
                onClick={handleCreate}
                className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-stone-300 dark:border-stone-600 rounded-lg text-stone-600 dark:text-stone-400 hover:border-teal-500 hover:text-teal-600 dark:hover:text-teal-400 transition-colors"
              >
                <Plus className="w-5 h-5" />
                新建配置
              </button>
            </>
          ) : (
            /* Form */
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  配置名称 *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  placeholder="例如：内部网关、OpenAI"
                  className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  描述
                </label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="可选的配置描述"
                  className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  API 地址 *
                </label>
                <input
                  type="url"
                  value={formData.base_url}
                  onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                  required
                  placeholder="https://api.openai.com/v1"
                  className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  API 密钥 {mode === 'edit' ? '(留空保持不变)' : '*'}
                </label>
                <div className="relative">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={formData.api_key}
                    onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                    required={mode === 'create'}
                    placeholder={mode === 'edit' ? '••••••••' : 'sk-...'}
                    className="w-full px-4 py-2 pr-10 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600"
                  >
                    {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  可用模型 * (逗号分隔)
                </label>
                <input
                  type="text"
                  value={formData.available_models}
                  onChange={(e) => setFormData({ ...formData, available_models: e.target.value })}
                  required
                  placeholder="gpt-4, gpt-4-turbo, gpt-3.5-turbo"
                  className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  默认模型
                </label>
                <input
                  type="text"
                  value={formData.default_model}
                  onChange={(e) => setFormData({ ...formData, default_model: e.target.value })}
                  placeholder="留空则使用第一个可用模型"
                  className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  超时时间 (毫秒)
                </label>
                <input
                  type="number"
                  value={formData.timeout_ms}
                  onChange={(e) => setFormData({ ...formData, timeout_ms: parseInt(e.target.value) })}
                  min={5000}
                  max={300000}
                  className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                />
              </div>

              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.enabled}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                    className="w-4 h-4 rounded border-stone-300 text-teal-600 focus:ring-teal-500"
                  />
                  <span className="text-sm text-stone-700 dark:text-stone-300">启用</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_default}
                    onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                    className="w-4 h-4 rounded border-stone-300 text-teal-600 focus:ring-teal-500"
                  />
                  <span className="text-sm text-stone-700 dark:text-stone-300">设为默认</span>
                </label>
              </div>

              {/* Form Actions */}
              <div className="flex items-center gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setMode('list')
                    setEditingId(null)
                    setFormData(initialFormData)
                    setError(null)
                  }}
                  className="flex-1 px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors disabled:opacity-50"
                >
                  {isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      保存中...
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      保存
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
