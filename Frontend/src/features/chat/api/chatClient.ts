/**
 * Chat API Client
 *
 * Handles all chat-related API calls.
 * Uses shared API configuration for consistent base URL handling.
 */

import axios from 'axios'
import { API_CONFIG } from '@shared/config/api'

const API_BASE = API_CONFIG.BASE_URL

// Types
export interface ModelProfile {
  id: string
  name: string
  description?: string
  base_url: string
  has_api_key: boolean
  default_model: string
  available_models: string[]
  capabilities: string[]
  timeout_ms: number
  enabled: boolean
  is_default: boolean
  created_at: string
}

export interface Conversation {
  id: string
  title: string
  pinned: boolean
  model_profile_id?: string
  model?: string
  settings: Record<string, any>
  message_count: number
  last_message_at?: string
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: any
  model?: string
  prompt_tokens?: number
  completion_tokens?: number
  created_at: string
}

export interface Attachment {
  id: string
  file_name: string
  mime_type: string
  size_bytes: number
  extraction_status: string
  embedding_status: string
  chunk_count: number
  created_at: string
}

export interface StreamEvent {
  type: 'start' | 'delta' | 'tool_call' | 'tool_result' | 'done' | 'error' | 'conversation' | 'finish'
  data?: any
  error?: string
}

// API Client
class ChatClient {
  // Model Profiles
  async getModelProfiles(capability?: string): Promise<ModelProfile[]> {
    const params = capability ? { capability } : {}
    const response = await axios.get(`${API_BASE}/api/chat/model-profiles`, { params })
    return response.data
  }

  async createModelProfile(data: Partial<ModelProfile> & { api_key?: string }): Promise<ModelProfile> {
    const response = await axios.post(`${API_BASE}/api/chat/model-profiles`, data)
    return response.data
  }

  async updateModelProfile(id: string, data: Partial<ModelProfile> & { api_key?: string }): Promise<ModelProfile> {
    const response = await axios.patch(`${API_BASE}/api/chat/model-profiles/${id}`, data)
    return response.data
  }

  async deleteModelProfile(id: string): Promise<void> {
    await axios.delete(`${API_BASE}/api/chat/model-profiles/${id}`)
  }

  // Conversations
  async getConversations(params?: {
    limit?: number
    offset?: number
    search?: string
  }): Promise<{ data: Conversation[]; total: number }> {
    const response = await axios.get(`${API_BASE}/api/chat/conversations`, { params })
    return response.data
  }

  async createConversation(data: {
    title?: string
    model_profile_id?: string
    model?: string
    settings?: Record<string, any>
  }): Promise<Conversation> {
    const response = await axios.post(`${API_BASE}/api/chat/conversations`, data)
    return response.data
  }

  async getConversation(id: string): Promise<Conversation> {
    const response = await axios.get(`${API_BASE}/api/chat/conversations/${id}`)
    return response.data
  }

  async updateConversation(id: string, data: {
    title?: string
    pinned?: boolean
    model_profile_id?: string
    model?: string
    settings?: Record<string, any>
  }): Promise<Conversation> {
    const response = await axios.patch(`${API_BASE}/api/chat/conversations/${id}`, data)
    return response.data
  }

  async deleteConversation(id: string): Promise<void> {
    await axios.delete(`${API_BASE}/api/chat/conversations/${id}`)
  }

  // Messages
  async getMessages(conversationId: string, params?: {
    limit?: number
    before_id?: string
  }): Promise<Message[]> {
    const response = await axios.get(
      `${API_BASE}/api/chat/conversations/${conversationId}/messages`,
      { params }
    )
    return response.data
  }

  // Streaming message send
  sendMessage(
    conversationId: string,
    content: string,
    attachmentIds?: string[],
    onEvent: (event: StreamEvent) => void
  ): AbortController {
    const controller = new AbortController()

    const fetchStream = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/chat/conversations/${conversationId}/send`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              content,
              attachment_ids: attachmentIds,
            }),
            signal: controller.signal,
          }
        )

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('No response body')
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()

          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6)
              if (data === '[DONE]') {
                return
              }
              try {
                const event = JSON.parse(data) as StreamEvent
                onEvent(event)
              } catch {
                // Ignore parse errors
              }
            }
          }
        }
      } catch (error) {
        if ((error as Error).name !== 'AbortError') {
          onEvent({
            type: 'error',
            error: (error as Error).message,
          })
        }
      }
    }

    fetchStream()
    return controller
  }

  // Regenerate message
  regenerateMessage(
    conversationId: string,
    messageId: string,
    onEvent: (event: StreamEvent) => void
  ): AbortController {
    const controller = new AbortController()

    const fetchStream = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/chat/conversations/${conversationId}/regenerate/${messageId}`,
          {
            method: 'POST',
            signal: controller.signal,
          }
        )

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('No response body')
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()

          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6)
              if (data === '[DONE]') {
                return
              }
              try {
                const event = JSON.parse(data) as StreamEvent
                onEvent(event)
              } catch {
                // Ignore parse errors
              }
            }
          }
        }
      } catch (error) {
        if ((error as Error).name !== 'AbortError') {
          onEvent({
            type: 'error',
            error: (error as Error).message,
          })
        }
      }
    }

    fetchStream()
    return controller
  }

  // File upload
  async uploadFile(
    conversationId: string,
    file: File,
    usageMode: 'retrieval' | 'direct' | 'both' = 'retrieval'
  ): Promise<Attachment> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('usage_mode', usageMode)

    const response = await axios.post(
      `${API_BASE}/api/chat/conversations/${conversationId}/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )
    return response.data
  }

  async getAttachments(conversationId: string): Promise<Attachment[]> {
    const response = await axios.get(
      `${API_BASE}/api/chat/conversations/${conversationId}/attachments`
    )
    return response.data
  }

  async deleteAttachment(attachmentId: string): Promise<void> {
    await axios.delete(`${API_BASE}/api/chat/attachments/${attachmentId}`)
  }
}

export const chatClient = new ChatClient()
