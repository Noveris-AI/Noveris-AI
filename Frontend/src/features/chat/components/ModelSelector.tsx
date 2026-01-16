/**
 * Model Selector Component
 *
 * Dropdown for selecting model profiles and specific models.
 */

import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Settings, Check, Zap, Cloud, Server, Plus, Edit2 } from 'lucide-react'
import { ModelProfile } from '../api/chatClient'

interface ModelSelectorProps {
  profiles: ModelProfile[]
  selectedProfileId?: string
  selectedModel?: string
  onChange: (profileId: string, model: string) => void
  onSettingsClick: () => void
  onEditProfile?: (profile: ModelProfile) => void
}

export function ModelSelector({
  profiles,
  selectedProfileId,
  selectedModel,
  onChange,
  onSettingsClick,
  onEditProfile,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [expandedProfile, setExpandedProfile] = useState<string | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setExpandedProfile(null)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const currentProfile = profiles.find(p => p.id === selectedProfileId)
  const displayModel = selectedModel || currentProfile?.default_model || '选择模型'

  const getProfileIcon = (profile: ModelProfile) => {
    if (profile.name.toLowerCase().includes('gateway') || profile.name.toLowerCase().includes('内部')) {
      return Server
    }
    if (profile.name.toLowerCase().includes('openai')) {
      return Zap
    }
    return Cloud
  }

  const handleSelectModel = (profileId: string, model: string) => {
    onChange(profileId, model)
    setIsOpen(false)
    setExpandedProfile(null)
  }

  const handleEditClick = (e: React.MouseEvent, profile: ModelProfile) => {
    e.stopPropagation()
    setIsOpen(false)
    onEditProfile?.(profile)
  }

  const enabledProfiles = profiles.filter(p => p.enabled)

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg hover:border-stone-300 dark:hover:border-stone-600 transition-colors"
      >
        <div className="flex items-center gap-3">
          {currentProfile && (
            <div className="w-8 h-8 rounded-lg bg-teal-100 dark:bg-teal-900/30 flex items-center justify-center">
              {(() => {
                const Icon = getProfileIcon(currentProfile)
                return <Icon className="w-4 h-4 text-teal-600 dark:text-teal-400" />
              })()}
            </div>
          )}
          <div className="text-left">
            <div className="text-sm font-medium text-stone-900 dark:text-stone-100">
              {currentProfile?.name || '选择配置'}
            </div>
            <div className="text-xs text-stone-500 dark:text-stone-400">
              {displayModel}
            </div>
          </div>
        </div>
        <ChevronDown
          className={`w-4 h-4 text-stone-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg shadow-lg z-30 overflow-hidden">
          {/* Profiles List */}
          <div className="max-h-80 overflow-y-auto">
            {enabledProfiles.length === 0 ? (
              <div className="px-4 py-6 text-center text-stone-500 dark:text-stone-400">
                <p className="text-sm">暂无可用配置</p>
                <button
                  onClick={() => {
                    setIsOpen(false)
                    onSettingsClick()
                  }}
                  className="mt-2 text-sm text-teal-600 hover:text-teal-700 dark:text-teal-400"
                >
                  添加配置
                </button>
              </div>
            ) : (
              enabledProfiles.map(profile => {
                const Icon = getProfileIcon(profile)
                const isExpanded = expandedProfile === profile.id
                const isSelected = profile.id === selectedProfileId

                return (
                  <div key={profile.id} className="group">
                    <div
                      className={`flex items-center gap-3 px-4 py-3 hover:bg-stone-50 dark:hover:bg-stone-700/50 ${
                        isSelected ? 'bg-teal-50 dark:bg-teal-900/20' : ''
                      }`}
                    >
                      <button
                        onClick={() => {
                          if (profile.available_models.length > 1) {
                            setExpandedProfile(isExpanded ? null : profile.id)
                          } else {
                            handleSelectModel(profile.id, profile.default_model)
                          }
                        }}
                        className="flex items-center gap-3 flex-1 text-left"
                      >
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                          isSelected
                            ? 'bg-teal-100 dark:bg-teal-900/50'
                            : 'bg-stone-100 dark:bg-stone-700'
                        }`}>
                          <Icon className={`w-4 h-4 ${
                            isSelected
                              ? 'text-teal-600 dark:text-teal-400'
                              : 'text-stone-500 dark:text-stone-400'
                          }`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={`text-sm font-medium ${
                              isSelected
                                ? 'text-teal-700 dark:text-teal-300'
                                : 'text-stone-900 dark:text-stone-100'
                            }`}>
                              {profile.name}
                            </span>
                            {profile.is_default && (
                              <span className="px-1.5 py-0.5 bg-teal-100 dark:bg-teal-900/30 text-teal-600 dark:text-teal-400 text-xs rounded">
                                默认
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-stone-500 dark:text-stone-400">
                            {profile.available_models.length} 个模型可用
                          </div>
                        </div>
                        {profile.available_models.length > 1 && (
                          <ChevronDown
                            className={`w-4 h-4 text-stone-400 transition-transform ${
                              isExpanded ? 'rotate-180' : ''
                            }`}
                          />
                        )}
                        {isSelected && profile.available_models.length === 1 && (
                          <Check className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                        )}
                      </button>
                      {/* Edit button */}
                      <button
                        onClick={(e) => handleEditClick(e, profile)}
                        className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-stone-200 dark:hover:bg-stone-600 rounded transition-all"
                        title="编辑配置"
                      >
                        <Edit2 className="w-3.5 h-3.5 text-stone-500 dark:text-stone-400" />
                      </button>
                    </div>

                    {/* Models submenu */}
                    {isExpanded && profile.available_models.length > 1 && (
                      <div className="bg-stone-50 dark:bg-stone-900/50 border-t border-stone-100 dark:border-stone-700">
                        {profile.available_models.map(model => {
                          const isModelSelected = isSelected && selectedModel === model

                          return (
                            <button
                              key={model}
                              onClick={() => handleSelectModel(profile.id, model)}
                              className={`w-full flex items-center justify-between px-4 py-2 pl-16 hover:bg-stone-100 dark:hover:bg-stone-700/50 ${
                                isModelSelected ? 'bg-teal-50 dark:bg-teal-900/20' : ''
                              }`}
                            >
                              <span className={`text-sm ${
                                isModelSelected
                                  ? 'text-teal-700 dark:text-teal-300 font-medium'
                                  : 'text-stone-700 dark:text-stone-300'
                              }`}>
                                {model}
                              </span>
                              {isModelSelected && (
                                <Check className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                              )}
                            </button>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>

          {/* Add New Config Button */}
          <div className="border-t border-stone-200 dark:border-stone-700">
            <button
              onClick={() => {
                setIsOpen(false)
                onSettingsClick()
              }}
              className="w-full flex items-center gap-2 px-4 py-3 text-sm text-teal-600 dark:text-teal-400 hover:bg-stone-50 dark:hover:bg-stone-700/50"
            >
              <Plus className="w-4 h-4" />
              添加模型配置
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
