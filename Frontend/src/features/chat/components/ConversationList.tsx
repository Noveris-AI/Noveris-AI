/**
 * Conversation List Component
 *
 * Displays the list of chat conversations in the sidebar.
 */

import { useState } from 'react'
import { Pin, Trash2, Edit2, MoreVertical, MessageSquare } from 'lucide-react'
import { Conversation } from '../api/chatClient'

interface ConversationListProps {
  conversations: Conversation[]
  selectedId: string | null
  isLoading: boolean
  onSelect: (id: string) => void
  onPin: (id: string) => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
}

export function ConversationList({
  conversations,
  selectedId,
  isLoading,
  onSelect,
  onPin,
  onRename,
  onDelete,
}: ConversationListProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [menuOpen, setMenuOpen] = useState<string | null>(null)

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))

    if (days === 0) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    } else if (days === 1) {
      return '昨天'
    } else if (days < 7) {
      return `${days}天前`
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
    }
  }

  const handleStartEdit = (conv: Conversation) => {
    setEditingId(conv.id)
    setEditTitle(conv.title)
    setMenuOpen(null)
  }

  const handleSaveEdit = (id: string) => {
    if (editTitle.trim()) {
      onRename(id, editTitle.trim())
    }
    setEditingId(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent, id: string) => {
    if (e.key === 'Enter') {
      handleSaveEdit(id)
    } else if (e.key === 'Escape') {
      setEditingId(null)
    }
  }

  // Group conversations by pinned status
  const pinnedConversations = conversations.filter(c => c.pinned)
  const regularConversations = conversations.filter(c => !c.pinned)

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-teal-600"></div>
      </div>
    )
  }

  if (conversations.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="text-center text-stone-500 dark:text-stone-400">
          <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">暂无对话</p>
        </div>
      </div>
    )
  }

  const renderConversation = (conv: Conversation) => (
    <div
      key={conv.id}
      className={`group relative px-4 py-3 cursor-pointer transition-colors ${
        selectedId === conv.id
          ? 'bg-teal-50 dark:bg-teal-900/20 border-r-2 border-teal-500'
          : 'hover:bg-stone-100 dark:hover:bg-stone-800'
      }`}
      onClick={() => onSelect(conv.id)}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          {editingId === conv.id ? (
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onBlur={() => handleSaveEdit(conv.id)}
              onKeyDown={(e) => handleKeyDown(e, conv.id)}
              onClick={(e) => e.stopPropagation()}
              className="w-full px-2 py-1 text-sm bg-white dark:bg-stone-700 border border-teal-500 rounded focus:outline-none"
              autoFocus
            />
          ) : (
            <>
              <div className="flex items-center gap-2">
                {conv.pinned && (
                  <Pin className="w-3 h-3 text-teal-500 flex-shrink-0" />
                )}
                <h3 className="text-sm font-medium text-stone-900 dark:text-stone-100 truncate">
                  {conv.title}
                </h3>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-stone-500 dark:text-stone-400">
                  {conv.message_count} 条消息
                </span>
                <span className="text-xs text-stone-400 dark:text-stone-500">
                  {formatDate(conv.last_message_at || conv.updated_at)}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Actions Menu */}
        <div
          className={`relative ${
            menuOpen === conv.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
          } transition-opacity`}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => setMenuOpen(menuOpen === conv.id ? null : conv.id)}
            className="p-1 hover:bg-stone-200 dark:hover:bg-stone-700 rounded"
          >
            <MoreVertical className="w-4 h-4 text-stone-500" />
          </button>

          {menuOpen === conv.id && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setMenuOpen(null)}
              />
              <div className="absolute right-0 top-full mt-1 w-36 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-20 py-1">
                <button
                  onClick={() => {
                    onPin(conv.id)
                    setMenuOpen(null)
                  }}
                  className="w-full px-3 py-2 text-left text-sm hover:bg-stone-100 dark:hover:bg-stone-700 flex items-center gap-2"
                >
                  <Pin className="w-4 h-4" />
                  {conv.pinned ? '取消置顶' : '置顶'}
                </button>
                <button
                  onClick={() => handleStartEdit(conv)}
                  className="w-full px-3 py-2 text-left text-sm hover:bg-stone-100 dark:hover:bg-stone-700 flex items-center gap-2"
                >
                  <Edit2 className="w-4 h-4" />
                  重命名
                </button>
                <button
                  onClick={() => {
                    onDelete(conv.id)
                    setMenuOpen(null)
                  }}
                  className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
                >
                  <Trash2 className="w-4 h-4" />
                  删除
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )

  return (
    <div className="flex-1 overflow-y-auto">
      {pinnedConversations.length > 0 && (
        <div>
          <div className="px-4 py-2 text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
            置顶
          </div>
          {pinnedConversations.map(renderConversation)}
        </div>
      )}

      {regularConversations.length > 0 && (
        <div>
          {pinnedConversations.length > 0 && (
            <div className="px-4 py-2 text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
              最近
            </div>
          )}
          {regularConversations.map(renderConversation)}
        </div>
      )}
    </div>
  )
}
