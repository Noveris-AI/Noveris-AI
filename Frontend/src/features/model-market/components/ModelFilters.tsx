import { useState } from 'react'
import type { PipelineTag, SortBy, SortOrder } from '../api/modelMarketTypes'

interface ModelFiltersProps {
  pipelineTags: Array<{ tag: string; name: string; count: number }>
  categories: Array<{ category: string; count: number }>
  onFilterChange: (filters: ModelFiltersState) => void
  loading?: boolean
}

export interface ModelFiltersState {
  query: string
  pipelineTag: PipelineTag | ''
  author: string
  tags: string[]
  categories: string[]
  sortBy: SortBy
  sortOrder: SortOrder
}

const SORT_OPTIONS: Array<{ value: SortBy; label: string }> = [
  { value: 'last_modified', label: '最近更新' },
  { value: 'downloads', label: '下载量' },
  { value: 'likes', label: '点赞数' },
  { value: 'model_name', label: '模型名称' },
  { value: 'author', label: '作者' },
]

export function ModelFilters({
  pipelineTags,
  onFilterChange,
  loading = false,
}: ModelFiltersProps) {

  const [filters, setFilters] = useState<ModelFiltersState>({
    query: '',
    pipelineTag: '',
    author: '',
    tags: [],
    categories: [],
    sortBy: 'last_modified',
    sortOrder: 'desc',
  })

  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['pipeline', 'sort'])
  )

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections)
    if (newExpanded.has(section)) {
      newExpanded.delete(section)
    } else {
      newExpanded.add(section)
    }
    setExpandedSections(newExpanded)
  }

  const updateFilter = (key: keyof ModelFiltersState, value: any) => {
    const newFilters = { ...filters, [key]: value }
    setFilters(newFilters)
    onFilterChange(newFilters)
  }

  const handleSearch = () => {
    onFilterChange(filters)
  }

  const handleReset = () => {
    const resetFilters: ModelFiltersState = {
      query: '',
      pipelineTag: '',
      author: '',
      tags: [],
      categories: [],
      sortBy: 'last_modified',
      sortOrder: 'desc',
    }
    setFilters(resetFilters)
    onFilterChange(resetFilters)
  }

  return (
    <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 p-4 sticky top-6">
      {/* Search */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
          搜索
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={filters.query}
            onChange={(e) => updateFilter('query', e.target.value)}
            placeholder="模型名称、描述或作者..."
            className="flex-1 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 dark:placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            disabled={loading}
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '搜索中...' : '搜索'}
          </button>
        </div>
      </div>

      {/* Pipeline Tags */}
      <div className="mb-4">
        <button
          onClick={() => toggleSection('pipeline')}
          className="flex items-center justify-between w-full text-sm font-medium text-stone-700 dark:text-stone-300 mb-2"
        >
          <span>模型类型</span>
          <svg
            className={`w-4 h-4 transition-transform ${expandedSections.has('pipeline') ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {expandedSections.has('pipeline') && (
          <div className="space-y-1 max-h-48 overflow-y-auto">
            <button
              onClick={() => updateFilter('pipelineTag', '')}
              className={`w-full text-left px-3 py-1.5 text-sm rounded-lg transition-colors ${
                filters.pipelineTag === ''
                  ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 font-medium'
                  : 'text-stone-600 dark:text-stone-400 hover:bg-stone-50 dark:hover:bg-stone-700'
              }`}
            >
              全部 ({pipelineTags.reduce((sum, t) => sum + t.count, 0)})
            </button>
            {pipelineTags.map((tag) => (
              <button
                key={tag.tag}
                onClick={() => updateFilter('pipelineTag', tag.tag as PipelineTag)}
                className={`w-full text-left px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  filters.pipelineTag === tag.tag
                    ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 font-medium'
                    : 'text-stone-600 dark:text-stone-400 hover:bg-stone-50 dark:hover:bg-stone-700'
                }`}
              >
                {tag.name} ({tag.count})
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Sort */}
      <div className="mb-4">
        <button
          onClick={() => toggleSection('sort')}
          className="flex items-center justify-between w-full text-sm font-medium text-stone-700 dark:text-stone-300 mb-2"
        >
          <span>排序</span>
          <svg
            className={`w-4 h-4 transition-transform ${expandedSections.has('sort') ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {expandedSections.has('sort') && (
          <div className="space-y-2">
            <select
              value={filters.sortBy}
              onChange={(e) => updateFilter('sortBy', e.target.value as SortBy)}
              className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
              disabled={loading}
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <button
                onClick={() => updateFilter('sortOrder', 'desc')}
                className={`flex-1 px-3 py-2 text-sm rounded-lg transition-colors ${
                  filters.sortOrder === 'desc'
                    ? 'bg-teal-600 text-white'
                    : 'bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-200 dark:hover:bg-stone-600'
                }`}
                disabled={loading}
              >
                降序
              </button>
              <button
                onClick={() => updateFilter('sortOrder', 'asc')}
                className={`flex-1 px-3 py-2 text-sm rounded-lg transition-colors ${
                  filters.sortOrder === 'asc'
                    ? 'bg-teal-600 text-white'
                    : 'bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 hover:bg-stone-200 dark:hover:bg-stone-600'
                }`}
                disabled={loading}
              >
                升序
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Reset */}
      <button
        onClick={handleReset}
        disabled={loading}
        className="w-full px-4 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        重置筛选
      </button>
    </div>
  )
}
