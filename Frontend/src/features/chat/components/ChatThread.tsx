/**
 * Chat Thread Component
 *
 * Displays the message history and streaming content.
 */

import { useEffect, useRef, useState } from 'react'
import { Copy, Check, RefreshCw, User, Bot, Wrench } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Message } from '../api/chatClient'

interface ChatThreadProps {
  messages: Message[]
  streamingContent: string
  isStreaming: boolean
  onRegenerate: (messageId: string) => void
}

export function ChatThread({
  messages,
  streamingContent,
  isStreaming,
  onRegenerate,
}: ChatThreadProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Auto-scroll to bottom when new messages arrive or streaming
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamingContent])

  const handleCopy = async (content: string, id: string) => {
    await navigator.clipboard.writeText(content)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const formatContent = (content: any): string => {
    if (typeof content === 'string') return content
    if (Array.isArray(content)) {
      return content
        .filter(item => item.type === 'text')
        .map(item => item.text)
        .join('\n')
    }
    return JSON.stringify(content, null, 2)
  }

  const renderMessage = (message: Message, isLast: boolean) => {
    const content = formatContent(message.content)
    const isUser = message.role === 'user'
    const isTool = message.role === 'tool'

    if (isTool) {
      return (
        <div key={message.id} className="py-2">
          <div className="flex items-start gap-3 max-w-4xl mx-auto px-6">
            <div className="w-8 h-8 rounded-lg bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center flex-shrink-0">
              <Wrench className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
                工具调用结果
              </div>
              <pre className="text-sm bg-stone-100 dark:bg-stone-800 rounded-lg p-3 overflow-x-auto">
                <code>{content}</code>
              </pre>
            </div>
          </div>
        </div>
      )
    }

    return (
      <div
        key={message.id}
        className={`py-6 ${isUser ? 'bg-white dark:bg-stone-800' : 'bg-stone-50 dark:bg-stone-900/50'}`}
      >
        <div className="flex items-start gap-4 max-w-4xl mx-auto px-6">
          {/* Avatar */}
          <div
            className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
              isUser
                ? 'bg-teal-100 dark:bg-teal-900/30'
                : 'bg-purple-100 dark:bg-purple-900/30'
            }`}
          >
            {isUser ? (
              <User className="w-4 h-4 text-teal-600 dark:text-teal-400" />
            ) : (
              <Bot className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-medium text-sm text-stone-900 dark:text-stone-100">
                {isUser ? '你' : 'AI 助手'}
              </span>
              {message.model && !isUser && (
                <span className="text-xs text-stone-500 dark:text-stone-400">
                  {message.model}
                </span>
              )}
            </div>

            <div className="prose prose-stone dark:prose-invert max-w-none prose-pre:p-0 prose-pre:bg-transparent">
              <ReactMarkdown
                components={{
                  code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '')
                    const codeString = String(children).replace(/\n$/, '')

                    if (!inline && match) {
                      return (
                        <div className="relative group">
                          <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={() => handleCopy(codeString, `code-${message.id}`)}
                              className="p-1.5 bg-stone-700 hover:bg-stone-600 rounded text-stone-300"
                            >
                              {copiedId === `code-${message.id}` ? (
                                <Check className="w-3.5 h-3.5" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                          <SyntaxHighlighter
                            style={oneDark}
                            language={match[1]}
                            PreTag="div"
                            className="rounded-lg !mt-0"
                            {...props}
                          >
                            {codeString}
                          </SyntaxHighlighter>
                        </div>
                      )
                    }

                    return (
                      <code
                        className="px-1.5 py-0.5 bg-stone-200 dark:bg-stone-700 rounded text-sm"
                        {...props}
                      >
                        {children}
                      </code>
                    )
                  },
                }}
              >
                {content}
              </ReactMarkdown>
            </div>

            {/* Message Actions */}
            {!isUser && (
              <div className="flex items-center gap-2 mt-4 opacity-0 group-hover:opacity-100 hover:opacity-100 transition-opacity">
                <button
                  onClick={() => handleCopy(content, message.id)}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 hover:bg-stone-200 dark:hover:bg-stone-700 rounded transition-colors"
                >
                  {copiedId === message.id ? (
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
                {isLast && (
                  <button
                    onClick={() => onRegenerate(message.id)}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 hover:bg-stone-200 dark:hover:bg-stone-700 rounded transition-colors"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    重新生成
                  </button>
                )}
              </div>
            )}

            {/* Token usage */}
            {!isUser && message.prompt_tokens && (
              <div className="mt-2 text-xs text-stone-400 dark:text-stone-500">
                Tokens: {message.prompt_tokens} + {message.completion_tokens} = {(message.prompt_tokens || 0) + (message.completion_tokens || 0)}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  const lastAssistantIndex = messages.map(m => m.role).lastIndexOf('assistant')

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto">
      {messages.length === 0 && !isStreaming ? (
        <div className="h-full flex items-center justify-center">
          <div className="text-center text-stone-500 dark:text-stone-400">
            <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>发送消息开始对话</p>
          </div>
        </div>
      ) : (
        <>
          {messages.map((message, index) =>
            renderMessage(message, message.role === 'assistant' && index === lastAssistantIndex)
          )}

          {/* Streaming message */}
          {isStreaming && streamingContent && (
            <div className="py-6 bg-stone-50 dark:bg-stone-900/50">
              <div className="flex items-start gap-4 max-w-4xl mx-auto px-6">
                <div className="w-8 h-8 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-medium text-sm text-stone-900 dark:text-stone-100">
                      AI 助手
                    </span>
                    <span className="flex items-center gap-1 text-xs text-teal-600 dark:text-teal-400">
                      <span className="w-1.5 h-1.5 bg-teal-500 rounded-full animate-pulse"></span>
                      生成中...
                    </span>
                  </div>
                  <div className="prose prose-stone dark:prose-invert max-w-none">
                    <ReactMarkdown>{streamingContent}</ReactMarkdown>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Loading indicator when streaming but no content yet */}
          {isStreaming && !streamingContent && (
            <div className="py-6 bg-stone-50 dark:bg-stone-900/50">
              <div className="flex items-start gap-4 max-w-4xl mx-auto px-6">
                <div className="w-8 h-8 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-stone-900 dark:text-stone-100">
                      AI 助手
                    </span>
                  </div>
                  <div className="flex items-center gap-1 mt-2">
                    <span className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
