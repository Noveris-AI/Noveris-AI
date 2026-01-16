/**
 * Playground Page
 *
 * Multi-tab playground for testing various model capabilities.
 */

import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Code,
  List,
  Image,
  Mic,
  Video,
  Sparkles
} from 'lucide-react'
import { EmbeddingsTab } from '../components/EmbeddingsTab'
import { RerankTab } from '../components/RerankTab'
import { ImagesTab } from '../components/ImagesTab'
import { AudioTab } from '../components/AudioTab'

type TabId = 'embeddings' | 'rerank' | 'images' | 'audio' | 'video'

interface Tab {
  id: TabId
  label: string
  icon: React.ElementType
  description: string
  available: boolean
}

const tabs: Tab[] = [
  {
    id: 'embeddings',
    label: 'Embeddings',
    icon: Code,
    description: '将文本转换为向量表示',
    available: true,
  },
  {
    id: 'rerank',
    label: 'Rerank',
    icon: List,
    description: '对文档进行相关性重排序',
    available: true,
  },
  {
    id: 'images',
    label: 'Images',
    icon: Image,
    description: '根据描述生成图像',
    available: true,
  },
  {
    id: 'audio',
    label: 'Audio',
    icon: Mic,
    description: '语音识别和文字转语音',
    available: true,
  },
  {
    id: 'video',
    label: 'Video',
    icon: Video,
    description: '视频生成 (即将推出)',
    available: false,
  },
]

export default function PlaygroundPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = (searchParams.get('tab') as TabId) || 'embeddings'

  const handleTabChange = (tabId: TabId) => {
    setSearchParams({ tab: tabId })
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'embeddings':
        return <EmbeddingsTab />
      case 'rerank':
        return <RerankTab />
      case 'images':
        return <ImagesTab />
      case 'audio':
        return <AudioTab />
      case 'video':
        return (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Video className="w-16 h-16 mx-auto mb-4 text-stone-300 dark:text-stone-600" />
              <h3 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-2">
                视频生成
              </h3>
              <p className="text-stone-500 dark:text-stone-400">
                此功能即将推出，敬请期待
              </p>
            </div>
          </div>
        )
      default:
        return null
    }
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] -m-6">
      {/* Sidebar */}
      <div className="w-64 border-r border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-900 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-stone-200 dark:border-stone-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-stone-900 dark:text-stone-100">
                Playground
              </h1>
              <p className="text-xs text-stone-500 dark:text-stone-400">
                模型能力测试
              </p>
            </div>
          </div>
        </div>

        {/* Tab List */}
        <nav className="flex-1 p-2 space-y-1">
          {tabs.map(tab => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            const isDisabled = !tab.available

            return (
              <button
                key={tab.id}
                onClick={() => !isDisabled && handleTabChange(tab.id)}
                disabled={isDisabled}
                className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-colors text-left ${
                  isActive
                    ? 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300'
                    : isDisabled
                    ? 'text-stone-400 dark:text-stone-600 cursor-not-allowed'
                    : 'hover:bg-stone-100 dark:hover:bg-stone-800 text-stone-700 dark:text-stone-300'
                }`}
              >
                <Icon className={`w-5 h-5 ${
                  isActive
                    ? 'text-teal-600 dark:text-teal-400'
                    : isDisabled
                    ? 'text-stone-400 dark:text-stone-600'
                    : 'text-stone-500 dark:text-stone-400'
                }`} />
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-medium ${
                    isActive ? '' : isDisabled ? 'text-stone-400 dark:text-stone-600' : ''
                  }`}>
                    {tab.label}
                  </div>
                  <div className={`text-xs truncate ${
                    isActive
                      ? 'text-teal-600/70 dark:text-teal-400/70'
                      : 'text-stone-500 dark:text-stone-500'
                  }`}>
                    {tab.description}
                  </div>
                </div>
                {isDisabled && (
                  <span className="px-1.5 py-0.5 bg-stone-200 dark:bg-stone-700 text-stone-500 text-xs rounded">
                    Soon
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-stone-200 dark:border-stone-700">
          <p className="text-xs text-stone-500 dark:text-stone-400 text-center">
            使用配置的模型 API 进行测试
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col bg-white dark:bg-stone-800 overflow-hidden">
        {renderTabContent()}
      </div>
    </div>
  )
}
