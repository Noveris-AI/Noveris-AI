import { useNavigate } from 'react-router-dom'
import type { ModelCard } from '../api/modelMarketTypes'

interface ModelCardProps {
  model: ModelCard
  onClick?: (modelId: string) => void
}

const PIPELINE_TAG_NAMES: Record<string, string> = {
  'text-generation': '文本生成',
  'text2text-generation': '文本到文本生成',
  'fill-mask': '填空',
  'token-classification': '词元分类',
  'text-classification': '文本分类',
  'question-answering': '问答',
  'summarization': '摘要',
  'translation': '翻译',
  'sentence-similarity': '句相似度',
  'feature-extraction': '特征提取',
  'rerank': '重排序',
  'text-to-speech': '语音合成',
  'automatic-speech-recognition': '语音识别',
  'image-classification': '图像分类',
  'object-detection': '目标检测',
  'image-segmentation': '图像分割',
  'text-to-image': '文本生成图像',
  'image-to-image': '图像到图像',
  'zero-shot-classification': '零样本分类',
  'zero-shot-image-classification': '零样本图像分类',
  'reinforcement-learning': '强化学习',
  'robotics': '机器人',
  'tabular-classification': '表格分类',
  'tabular-regression': '表格回归',
  'audio-classification': '音频分类',
  'audio-to-audio': '音频到音频',
}

export function ModelCardComponent({ model }: ModelCardProps) {
  const navigate = useNavigate()

  const handleDeployClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigate('/dashboard/deployment')
  }

  const handleSourceClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    window.open(model.source_url, '_blank')
  }

  const pipelineTagName = model.pipeline_tag
    ? PIPELINE_TAG_NAMES[model.pipeline_tag] || model.pipeline_tag
    : null

  return (
    <div className="group bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 hover:border-teal-500 dark:hover:border-teal-400 transition-all shadow-sm hover:shadow-md h-full flex flex-col">
      {/* 上部：模型名称和标签 */}
      <div className="p-4 flex-1">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="font-semibold text-stone-900 dark:text-stone-100 text-base line-clamp-2 group-hover:text-teal-600 dark:group-hover:text-teal-400 transition-colors flex-1">
            {model.model_name || model.model_id}
          </h3>
          {pipelineTagName && (
            <span className="px-2 py-0.5 text-xs font-medium bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded-full shrink-0">
              {pipelineTagName}
            </span>
          )}
        </div>

        {/* 描述 */}
        {model.description && (
          <p className="text-sm text-stone-600 dark:text-stone-400 line-clamp-2 mb-3">
            {model.description}
          </p>
        )}

        {/* 统计信息 */}
        <div className="flex items-center gap-3 text-xs text-stone-500 dark:text-stone-500">
          <div className="flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span>{model.downloads.toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
            <span>{model.likes.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* 下部：按钮区域 */}
      <div className="p-4 pt-0 mt-auto border-t border-stone-100 dark:border-stone-700/50 flex gap-2">
        <button
          onClick={handleDeployClick}
          className="flex-1 px-3 py-2 text-sm font-medium bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors flex items-center justify-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          部署
        </button>
        <button
          onClick={handleSourceClick}
          className="px-3 py-2 text-sm font-medium bg-stone-100 hover:bg-stone-200 dark:bg-stone-700 dark:hover:bg-stone-600 text-stone-700 dark:text-stone-300 rounded-lg transition-colors flex items-center justify-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
          源码
        </button>
      </div>
    </div>
  )
}
