import { useState, useRef, useEffect } from 'react'
import { modelMarketClient } from '../api/modelMarketClient'
import type { AIRecommendModel } from '../api/modelMarketTypes'

interface AIRecommendChatProps {
  onModelSelect?: (modelId: string) => void
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  recommendations?: AIRecommendModel[]
}

export function AIRecommendChat({ onModelSelect }: AIRecommendChatProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: '你好！我是 AI 模型推荐助手。告诉我你想要什么类型的模型，我可以帮你推荐最合适的 Hugging Face 模型。\n\n例如：\n- "推荐一个 rerank 模型"\n- "我需要一个中文文本生成模型"\n- "推荐适合金融领域的大型语言模型"',
    },
  ])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')

    // Add user message
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)

    try {
      const response = await modelMarketClient.aiRecommend({
        query: userMessage,
        max_results: 5,
      })

      // Add assistant message with recommendations
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `为你找到 ${response.total_found} 个推荐模型：`,
          recommendations: response.recommendations,
        },
      ])
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `抱歉，推荐服务暂时不可用。${error instanceof Error ? error.message : ''}`,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-teal-600 hover:bg-teal-700 text-white rounded-full shadow-lg flex items-center justify-center transition-colors z-50"
        title="AI 推荐"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
      </button>
    )
  }

  return (
    <div className="fixed bottom-6 right-6 w-96 h-[32rem] bg-white dark:bg-stone-800 rounded-xl shadow-2xl border border-stone-200 dark:border-stone-700 flex flex-col z-50">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-stone-200 dark:border-stone-700">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-teal-100 dark:bg-teal-900/30 rounded-full flex items-center justify-center">
            <svg className="w-5 h-5 text-teal-600 dark:text-teal-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h3 className="font-semibold text-stone-900 dark:text-stone-100">AI 模型推荐</h3>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="p-1 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 ${
                message.role === 'user'
                  ? 'bg-teal-600 text-white'
                  : 'bg-stone-100 dark:bg-stone-700 text-stone-800 dark:text-stone-200'
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              {message.recommendations && (
                <div className="mt-3 space-y-2">
                  {message.recommendations.map((rec) => (
                    <div
                      key={rec.model_id}
                      onClick={() => {
                        onModelSelect?.(rec.model_id)
                        setIsOpen(false)
                      }}
                      className="bg-white dark:bg-stone-800 rounded-lg p-2 cursor-pointer hover:ring-2 hover:ring-teal-500 transition-all"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-stone-900 dark:text-stone-100 truncate">
                            {rec.model_name || rec.model_id}
                          </p>
                          {rec.author && (
                            <p className="text-xs text-stone-500 dark:text-stone-400">by {rec.author}</p>
                          )}
                          {rec.pipeline_tag && (
                            <span className="inline-block mt-1 px-2 py-0.5 text-xs bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded-full">
                              {rec.pipeline_tag}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-stone-500 dark:text-stone-500">
                          <span className="flex items-center gap-1">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                            {rec.downloads >= 1000 ? `${(rec.downloads / 1000).toFixed(1)}K` : rec.downloads}
                          </span>
                        </div>
                      </div>
                      {rec.reason && (
                        <p className="mt-2 text-xs text-stone-600 dark:text-stone-400 line-clamp-2">
                          {rec.reason}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-stone-100 dark:bg-stone-700 rounded-lg px-3 py-2">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-stone-200 dark:border-stone-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="描述你想要的模型类型..."
            disabled={loading}
            className="flex-1 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg text-sm font-medium transition-colors disabled:cursor-not-allowed"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  )
}
