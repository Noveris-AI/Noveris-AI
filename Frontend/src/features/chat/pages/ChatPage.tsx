/**
 * Chat Page
 *
 * Main chat interface with conversation list and message thread.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  MessageSquare,
  Plus,
  Search,
  Pin,
  Trash2,
  Edit2,
  MoreVertical,
  Send,
  Paperclip,
  Globe,
  StopCircle,
  RefreshCw,
  Copy,
  Check,
  Settings,
  ChevronDown,
} from 'lucide-react'
import { chatClient, Conversation, Message, StreamEvent, ModelProfile } from '../api/chatClient'
import { ConversationList } from '../components/ConversationList'
import { ChatThread } from '../components/ChatThread'
import { Composer } from '../components/Composer'
import { ModelSelector } from '../components/ModelSelector'
import { ModelConfigDrawer } from '../components/ModelConfigDrawer'

export default function ChatPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  // State
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [showModelConfig, setShowModelConfig] = useState(false)
  const [editingProfile, setEditingProfile] = useState<ModelProfile | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const abortControllerRef = useRef<AbortController | null>(null)

  // Queries
  const { data: conversationsData, isLoading: loadingConversations } = useQuery({
    queryKey: ['conversations', searchQuery],
    queryFn: () => chatClient.getConversations({ limit: 50, search: searchQuery || undefined }),
  })

  const { data: modelProfiles } = useQuery({
    queryKey: ['model-profiles'],
    queryFn: () => chatClient.getModelProfiles(),
  })

  const { data: currentConversation } = useQuery({
    queryKey: ['conversation', selectedConversationId],
    queryFn: () => selectedConversationId ? chatClient.getConversation(selectedConversationId) : null,
    enabled: !!selectedConversationId,
  })

  const { data: messages, refetch: refetchMessages } = useQuery({
    queryKey: ['messages', selectedConversationId],
    queryFn: () => selectedConversationId ? chatClient.getMessages(selectedConversationId) : [],
    enabled: !!selectedConversationId,
  })

  // Mutations
  const createConversationMutation = useMutation({
    mutationFn: chatClient.createConversation.bind(chatClient),
    onSuccess: (conversation) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      setSelectedConversationId(conversation.id)
    },
  })

  const updateConversationMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      chatClient.updateConversation(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      queryClient.invalidateQueries({ queryKey: ['conversation'] })
    },
  })

  const deleteConversationMutation = useMutation({
    mutationFn: chatClient.deleteConversation.bind(chatClient),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      setSelectedConversationId(null)
    },
  })

  // Handlers
  const handleNewConversation = () => {
    const defaultProfile = modelProfiles?.find(p => p.is_default)
    createConversationMutation.mutate({
      model_profile_id: defaultProfile?.id,
      model: defaultProfile?.default_model,
    })
  }

  const handleSelectConversation = (id: string) => {
    if (isStreaming) {
      abortControllerRef.current?.abort()
      setIsStreaming(false)
      setStreamingContent('')
    }
    setSelectedConversationId(id)
  }

  const handleSendMessage = useCallback((content: string, attachmentIds?: string[]) => {
    if (!selectedConversationId || isStreaming) return

    setIsStreaming(true)
    setStreamingContent('')

    const handleEvent = (event: StreamEvent) => {
      switch (event.type) {
        case 'start':
          break
        case 'delta':
          setStreamingContent(prev => prev + (event.data?.content || ''))
          break
        case 'tool_call':
          // Handle tool calls if needed
          break
        case 'done':
          setIsStreaming(false)
          setStreamingContent('')
          refetchMessages()
          queryClient.invalidateQueries({ queryKey: ['conversation', selectedConversationId] })
          break
        case 'error':
          setIsStreaming(false)
          setStreamingContent('')
          console.error('Stream error:', event.error)
          break
      }
    }

    abortControllerRef.current = chatClient.sendMessage(
      selectedConversationId,
      content,
      attachmentIds,
      handleEvent
    )
  }, [selectedConversationId, isStreaming, refetchMessages, queryClient])

  const handleStopGeneration = () => {
    abortControllerRef.current?.abort()
    setIsStreaming(false)
    setStreamingContent('')
  }

  const handleRegenerateMessage = (messageId: string) => {
    if (!selectedConversationId || isStreaming) return

    setIsStreaming(true)
    setStreamingContent('')

    const handleEvent = (event: StreamEvent) => {
      switch (event.type) {
        case 'delta':
          setStreamingContent(prev => prev + (event.data?.content || ''))
          break
        case 'done':
          setIsStreaming(false)
          setStreamingContent('')
          refetchMessages()
          break
        case 'error':
          setIsStreaming(false)
          setStreamingContent('')
          break
      }
    }

    abortControllerRef.current = chatClient.regenerateMessage(
      selectedConversationId,
      messageId,
      handleEvent
    )
  }

  const handleModelChange = (profileId: string, model: string) => {
    if (selectedConversationId) {
      updateConversationMutation.mutate({
        id: selectedConversationId,
        data: { model_profile_id: profileId, model },
      })
    }
  }

  const handleSettingsChange = (settings: Record<string, any>) => {
    if (selectedConversationId) {
      updateConversationMutation.mutate({
        id: selectedConversationId,
        data: { settings },
      })
    }
  }

  // Get current model info
  const currentProfile = modelProfiles?.find(
    p => p.id === currentConversation?.model_profile_id
  )
  const currentModel = currentConversation?.model || currentProfile?.default_model

  return (
    <div className="flex h-[calc(100vh-4rem)] -m-6">
      {/* Conversation List Sidebar */}
      <div className="w-80 border-r border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-900 flex flex-col">
        {/* Model Selector */}
        <div className="p-4 border-b border-stone-200 dark:border-stone-700">
          <ModelSelector
            profiles={modelProfiles || []}
            selectedProfileId={currentConversation?.model_profile_id}
            selectedModel={currentModel}
            onChange={handleModelChange}
            onSettingsClick={() => {
              setEditingProfile(null)
              setShowModelConfig(true)
            }}
            onEditProfile={(profile) => {
              setEditingProfile(profile)
              setShowModelConfig(true)
            }}
          />
        </div>

        {/* Search and New Chat */}
        <div className="p-4 space-y-3">
          <button
            onClick={handleNewConversation}
            disabled={createConversationMutation.isPending}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            新建对话
          </button>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索对话..."
              className="w-full pl-10 pr-4 py-2 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
            />
          </div>
        </div>

        {/* Conversation List */}
        <ConversationList
          conversations={conversationsData?.data || []}
          selectedId={selectedConversationId}
          isLoading={loadingConversations}
          onSelect={handleSelectConversation}
          onPin={(id) => {
            const conv = conversationsData?.data.find(c => c.id === id)
            updateConversationMutation.mutate({
              id,
              data: { pinned: !conv?.pinned },
            })
          }}
          onRename={(id, title) => {
            updateConversationMutation.mutate({ id, data: { title } })
          }}
          onDelete={(id) => deleteConversationMutation.mutate(id)}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-white dark:bg-stone-800">
        {selectedConversationId ? (
          <>
            {/* Chat Header */}
            <div className="h-14 px-6 flex items-center justify-between border-b border-stone-200 dark:border-stone-700">
              <div className="flex items-center gap-3">
                <h2 className="font-medium text-stone-900 dark:text-stone-100">
                  {currentConversation?.title || '新对话'}
                </h2>
                {currentModel && (
                  <span className="px-2 py-0.5 bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-400 text-xs rounded">
                    {currentModel}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {currentConversation?.settings?.enable_web_search && (
                  <span className="flex items-center gap-1 px-2 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 text-xs rounded">
                    <Globe className="w-3 h-3" />
                    联网搜索
                  </span>
                )}
              </div>
            </div>

            {/* Messages Thread */}
            <ChatThread
              messages={messages || []}
              streamingContent={streamingContent}
              isStreaming={isStreaming}
              onRegenerate={handleRegenerateMessage}
            />

            {/* Composer */}
            <Composer
              conversationId={selectedConversationId}
              isStreaming={isStreaming}
              enableWebSearch={currentConversation?.settings?.enable_web_search}
              onSend={handleSendMessage}
              onStop={handleStopGeneration}
              onSettingsChange={handleSettingsChange}
            />
          </>
        ) : (
          /* Empty State */
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center max-w-md">
              <div className="w-16 h-16 bg-teal-100 dark:bg-teal-900/30 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <MessageSquare className="w-8 h-8 text-teal-600 dark:text-teal-400" />
              </div>
              <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-2">
                开始新对话
              </h3>
              <p className="text-stone-600 dark:text-stone-400 mb-6">
                选择一个现有对话或创建新对话来开始与 AI 助手交流。
              </p>
              <button
                onClick={handleNewConversation}
                className="inline-flex items-center gap-2 px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors"
              >
                <Plus className="w-5 h-5" />
                新建对话
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Model Config Drawer */}
      <ModelConfigDrawer
        isOpen={showModelConfig}
        onClose={() => {
          setShowModelConfig(false)
          setEditingProfile(null)
        }}
        editingProfile={editingProfile}
      />
    </div>
  )
}
