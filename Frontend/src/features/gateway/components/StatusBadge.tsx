/**
 * Gateway Status Badge Components
 */

import type { UpstreamType, LogPayloadMode } from '../api/gatewayTypes'

// =============================================================================
// Upstream Type Badge
// =============================================================================

interface UpstreamTypeBadgeProps {
  type: UpstreamType
}

const upstreamTypeConfig: Record<UpstreamType, { label: string; bg: string; text: string }> = {
  openai: {
    label: 'OpenAI',
    bg: 'bg-green-100 dark:bg-green-900/30',
    text: 'text-green-700 dark:text-green-300',
  },
  openai_compatible: {
    label: 'OpenAI 兼容',
    bg: 'bg-teal-100 dark:bg-teal-900/30',
    text: 'text-teal-700 dark:text-teal-300',
  },
  anthropic: {
    label: 'Anthropic',
    bg: 'bg-purple-100 dark:bg-purple-900/30',
    text: 'text-purple-700 dark:text-purple-300',
  },
  gemini: {
    label: 'Gemini',
    bg: 'bg-amber-100 dark:bg-amber-900/30',
    text: 'text-amber-700 dark:text-amber-300',
  },
  cohere: {
    label: 'Cohere',
    bg: 'bg-pink-100 dark:bg-pink-900/30',
    text: 'text-pink-700 dark:text-pink-300',
  },
  stable_diffusion: {
    label: 'Stable Diffusion',
    bg: 'bg-indigo-100 dark:bg-indigo-900/30',
    text: 'text-indigo-700 dark:text-indigo-300',
  },
  custom_http: {
    label: '自定义 HTTP',
    bg: 'bg-stone-100 dark:bg-stone-800',
    text: 'text-stone-700 dark:text-stone-300',
  },
}

export function UpstreamTypeBadge({ type }: UpstreamTypeBadgeProps) {
  const config = upstreamTypeConfig[type] || upstreamTypeConfig.custom_http

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  )
}

// =============================================================================
// Health Status Badge
// =============================================================================

interface HealthStatusBadgeProps {
  status: 'healthy' | 'unhealthy' | 'unknown'
  size?: 'sm' | 'md'
}

const healthConfig: Record<string, { label: string; bg: string; text: string; dot: string }> = {
  healthy: {
    label: '健康',
    bg: 'bg-green-100 dark:bg-green-900/30',
    text: 'text-green-600 dark:text-green-400',
    dot: 'bg-green-500',
  },
  unhealthy: {
    label: '异常',
    bg: 'bg-red-100 dark:bg-red-900/30',
    text: 'text-red-600 dark:text-red-400',
    dot: 'bg-red-500',
  },
  unknown: {
    label: '未知',
    bg: 'bg-stone-100 dark:bg-stone-800',
    text: 'text-stone-600 dark:text-stone-400',
    dot: 'bg-stone-400',
  },
}

export function HealthStatusBadge({ status, size = 'md' }: HealthStatusBadgeProps) {
  const config = healthConfig[status] || healthConfig.unknown

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full ${config.bg} ${config.text} ${
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  )
}

// =============================================================================
// Enabled Status Badge
// =============================================================================

interface EnabledStatusBadgeProps {
  enabled: boolean
  size?: 'sm' | 'md'
}

export function EnabledStatusBadge({ enabled, size = 'md' }: EnabledStatusBadgeProps) {
  const config = enabled
    ? {
        label: '启用',
        bg: 'bg-green-100 dark:bg-green-900/30',
        text: 'text-green-600 dark:text-green-400',
        dot: 'bg-green-500',
      }
    : {
        label: '禁用',
        bg: 'bg-stone-100 dark:bg-stone-800',
        text: 'text-stone-600 dark:text-stone-400',
        dot: 'bg-stone-400',
      }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full ${config.bg} ${config.text} ${
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  )
}

// =============================================================================
// Log Payload Mode Badge
// =============================================================================

interface LogPayloadModeBadgeProps {
  mode: LogPayloadMode
}

const logModeConfig: Record<LogPayloadMode, { label: string; bg: string; text: string }> = {
  none: {
    label: '不记录',
    bg: 'bg-stone-100 dark:bg-stone-800',
    text: 'text-stone-600 dark:text-stone-400',
  },
  metadata_only: {
    label: '仅元数据',
    bg: 'bg-blue-100 dark:bg-blue-900/30',
    text: 'text-blue-600 dark:text-blue-400',
  },
  sampled: {
    label: '采样',
    bg: 'bg-amber-100 dark:bg-amber-900/30',
    text: 'text-amber-600 dark:text-amber-400',
  },
  full_with_redaction: {
    label: '完整(脱敏)',
    bg: 'bg-green-100 dark:bg-green-900/30',
    text: 'text-green-600 dark:text-green-400',
  },
}

export function LogPayloadModeBadge({ mode }: LogPayloadModeBadgeProps) {
  const config = logModeConfig[mode] || logModeConfig.none

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  )
}

// =============================================================================
// HTTP Status Badge
// =============================================================================

interface HTTPStatusBadgeProps {
  status?: number
  size?: 'sm' | 'md'
}

export function HTTPStatusBadge({ status, size = 'md' }: HTTPStatusBadgeProps) {
  let config: { bg: string; text: string }

  if (!status) {
    config = { bg: 'bg-stone-100 dark:bg-stone-800', text: 'text-stone-600 dark:text-stone-400' }
  } else if (status >= 200 && status < 300) {
    config = { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-600 dark:text-green-400' }
  } else if (status >= 400 && status < 500) {
    config = { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-600 dark:text-amber-400' }
  } else {
    config = { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-600 dark:text-red-400' }
  }

  return (
    <span
      className={`inline-flex items-center rounded-full ${config.bg} ${config.text} ${
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
      }`}
    >
      {status || 'N/A'}
    </span>
  )
}

// =============================================================================
// Capability Badge
// =============================================================================

interface CapabilityBadgeProps {
  capability: string
}

const capabilityLabels: Record<string, string> = {
  chat_completions: 'Chat',
  completions: 'Completions',
  responses: 'Responses',
  embeddings: 'Embeddings',
  images_generations: 'Images',
  images_edits: 'Image Edit',
  images_variations: 'Image Var',
  audio_speech: 'TTS',
  audio_transcriptions: 'STT',
  audio_translations: 'Translation',
  moderations: 'Moderation',
  rerank: 'Rerank',
}

export function CapabilityBadge({ capability }: CapabilityBadgeProps) {
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-300">
      {capabilityLabels[capability] || capability}
    </span>
  )
}
