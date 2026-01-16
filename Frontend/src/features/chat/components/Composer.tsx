/**
 * Composer Component
 *
 * Message input area with file upload and settings.
 */

import { useState, useRef, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Send,
  Paperclip,
  Globe,
  StopCircle,
  X,
  FileText,
  Image as ImageIcon,
  File,
  Loader2,
} from 'lucide-react'
import { chatClient, Attachment } from '../api/chatClient'

interface ComposerProps {
  conversationId: string
  isStreaming: boolean
  enableWebSearch?: boolean
  onSend: (content: string, attachmentIds?: string[]) => void
  onStop: () => void
  onSettingsChange: (settings: Record<string, any>) => void
}

export function Composer({
  conversationId,
  isStreaming,
  enableWebSearch,
  onSend,
  onStop,
  onSettingsChange,
}: ComposerProps) {
  const [content, setContent] = useState('')
  const [pendingAttachments, setPendingAttachments] = useState<string[]>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  // Get attachments for the conversation
  const { data: attachments } = useQuery({
    queryKey: ['attachments', conversationId],
    queryFn: () => chatClient.getAttachments(conversationId),
  })

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: (file: File) => chatClient.uploadFile(conversationId, file),
    onSuccess: (attachment) => {
      queryClient.invalidateQueries({ queryKey: ['attachments', conversationId] })
      setPendingAttachments(prev => [...prev, attachment.id])
    },
  })

  // Delete attachment mutation
  const deleteMutation = useMutation({
    mutationFn: chatClient.deleteAttachment.bind(chatClient),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attachments', conversationId] })
    },
  })

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value)
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSend = () => {
    if (!content.trim() && pendingAttachments.length === 0) return
    if (isStreaming) return

    onSend(content.trim(), pendingAttachments.length > 0 ? pendingAttachments : undefined)
    setContent('')
    setPendingAttachments([])
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return

    Array.from(files).forEach(file => {
      uploadMutation.mutate(file)
    })

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [uploadMutation])

  const handleRemoveAttachment = (id: string) => {
    setPendingAttachments(prev => prev.filter(a => a !== id))
    deleteMutation.mutate(id)
  }

  const toggleWebSearch = () => {
    onSettingsChange({ enable_web_search: !enableWebSearch })
  }

  const getFileIcon = (mimeType: string) => {
    if (mimeType.startsWith('image/')) return ImageIcon
    if (mimeType.includes('pdf') || mimeType.includes('document')) return FileText
    return File
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // Get pending attachment details
  const pendingAttachmentDetails = pendingAttachments
    .map(id => attachments?.find(a => a.id === id))
    .filter(Boolean) as Attachment[]

  return (
    <div className="border-t border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-800 p-4">
      <div className="max-w-4xl mx-auto">
        {/* Pending Attachments */}
        {pendingAttachmentDetails.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {pendingAttachmentDetails.map(attachment => {
              const Icon = getFileIcon(attachment.mime_type)
              return (
                <div
                  key={attachment.id}
                  className="flex items-center gap-2 px-3 py-2 bg-stone-100 dark:bg-stone-700 rounded-lg"
                >
                  <Icon className="w-4 h-4 text-stone-500" />
                  <span className="text-sm text-stone-700 dark:text-stone-300 max-w-[150px] truncate">
                    {attachment.file_name}
                  </span>
                  <span className="text-xs text-stone-500">
                    {formatFileSize(attachment.size_bytes)}
                  </span>
                  {attachment.extraction_status === 'processing' && (
                    <Loader2 className="w-3 h-3 text-teal-500 animate-spin" />
                  )}
                  <button
                    onClick={() => handleRemoveAttachment(attachment.id)}
                    className="p-0.5 hover:bg-stone-200 dark:hover:bg-stone-600 rounded"
                  >
                    <X className="w-3.5 h-3.5 text-stone-500" />
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {/* Uploading indicator */}
        {uploadMutation.isPending && (
          <div className="flex items-center gap-2 mb-3 text-sm text-stone-500">
            <Loader2 className="w-4 h-4 animate-spin" />
            上传中...
          </div>
        )}

        {/* Input Area */}
        <div className="flex items-end gap-3">
          {/* Actions */}
          <div className="flex items-center gap-1">
            {/* File Upload */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFileSelect}
              accept=".txt,.md,.pdf,.doc,.docx,.html,.htm,.json,.csv,.xml,.py,.js,.ts,.jsx,.tsx,.java,.cpp,.c,.h,.css,.scss,.yaml,.yml"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isStreaming || uploadMutation.isPending}
              className="p-2 hover:bg-stone-100 dark:hover:bg-stone-700 rounded-lg transition-colors disabled:opacity-50"
              title="上传文件"
            >
              <Paperclip className="w-5 h-5 text-stone-500" />
            </button>

            {/* Web Search Toggle */}
            <button
              onClick={toggleWebSearch}
              disabled={isStreaming}
              className={`p-2 rounded-lg transition-colors disabled:opacity-50 ${
                enableWebSearch
                  ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                  : 'hover:bg-stone-100 dark:hover:bg-stone-700 text-stone-500'
              }`}
              title={enableWebSearch ? '关闭联网搜索' : '开启联网搜索'}
            >
              <Globe className="w-5 h-5" />
            </button>
          </div>

          {/* Textarea */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={content}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              placeholder="输入消息..."
              disabled={isStreaming}
              rows={1}
              className="w-full px-4 py-3 bg-stone-100 dark:bg-stone-700 border-0 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-teal-500/20 disabled:opacity-50 text-stone-900 dark:text-stone-100 placeholder-stone-500"
              style={{ minHeight: '48px', maxHeight: '200px' }}
            />
          </div>

          {/* Send/Stop Button */}
          {isStreaming ? (
            <button
              onClick={onStop}
              className="p-3 bg-red-600 hover:bg-red-700 text-white rounded-xl transition-colors"
              title="停止生成"
            >
              <StopCircle className="w-5 h-5" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!content.trim() && pendingAttachments.length === 0}
              className="p-3 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-xl transition-colors disabled:cursor-not-allowed"
              title="发送消息"
            >
              <Send className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Hints */}
        <div className="mt-2 text-xs text-stone-400 dark:text-stone-500 text-center">
          按 Enter 发送，Shift + Enter 换行
        </div>
      </div>
    </div>
  )
}
