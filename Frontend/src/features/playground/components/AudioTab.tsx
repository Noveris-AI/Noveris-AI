/**
 * Audio Tab Component
 *
 * Test audio transcription and text-to-speech.
 */

import { useState, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Mic,
  Play,
  Loader2,
  Upload,
  Volume2,
  FileAudio,
  AlertCircle,
  Pause,
  RotateCcw,
  Download,
  X,
} from 'lucide-react'
import { playgroundClient, AudioTranscriptionResponse } from '../api/playgroundClient'
import { chatClient } from '../../chat/api/chatClient'

type AudioMode = 'transcription' | 'tts'

const TTS_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
const LANGUAGES = [
  { code: '', label: '自动检测' },
  { code: 'zh', label: '中文' },
  { code: 'en', label: 'English' },
  { code: 'ja', label: '日本語' },
  { code: 'ko', label: '한국어' },
  { code: 'de', label: 'Deutsch' },
  { code: 'fr', label: 'Français' },
  { code: 'es', label: 'Español' },
]

export function AudioTab() {
  const [mode, setMode] = useState<AudioMode>('transcription')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [language, setLanguage] = useState('')
  const [ttsText, setTtsText] = useState('')
  const [voice, setVoice] = useState('alloy')
  const [speed, setSpeed] = useState(1.0)
  const [selectedProfileId, setSelectedProfileId] = useState<string>('')
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [transcriptionResult, setTranscriptionResult] = useState<AudioTranscriptionResponse | null>(null)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)

  // Get model profiles with audio capability
  const { data: profiles } = useQuery({
    queryKey: ['model-profiles-audio'],
    queryFn: () => chatClient.getModelProfiles('audio'),
  })

  // Transcription mutation
  const transcriptionMutation = useMutation({
    mutationFn: () =>
      playgroundClient.transcribeAudio({
        file: selectedFile!,
        model: selectedModel,
        model_profile_id: selectedProfileId || undefined,
        language: language || undefined,
      }),
    onSuccess: (data) => {
      setTranscriptionResult(data)
    },
  })

  // TTS mutation
  const ttsMutation = useMutation({
    mutationFn: () =>
      playgroundClient.textToSpeech({
        input: ttsText,
        model: selectedModel,
        model_profile_id: selectedProfileId || undefined,
        voice,
        speed,
      }),
    onSuccess: (data) => {
      setAudioBlob(data)
    },
  })

  const handleProfileChange = (profileId: string) => {
    setSelectedProfileId(profileId)
    const profile = profiles?.find(p => p.id === profileId)
    if (profile && profile.available_models.length > 0) {
      setSelectedModel(profile.available_models[0])
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setTranscriptionResult(null)
    }
  }

  const handlePlayPause = () => {
    if (!audioRef.current || !audioBlob) return

    if (isPlaying) {
      audioRef.current.pause()
    } else {
      const url = URL.createObjectURL(audioBlob)
      audioRef.current.src = url
      audioRef.current.play()
    }
    setIsPlaying(!isPlaying)
  }

  const handleDownloadAudio = () => {
    if (!audioBlob) return
    const url = URL.createObjectURL(audioBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'generated-speech.mp3'
    a.click()
    URL.revokeObjectURL(url)
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const canTranscribe = selectedFile && selectedModel
  const canGenerateSpeech = ttsText.trim() && selectedModel

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-stone-200 dark:border-stone-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
              <Mic className="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
                Audio
              </h2>
              <p className="text-sm text-stone-500 dark:text-stone-400">
                语音识别和文字转语音
              </p>
            </div>
          </div>

          {/* Mode Tabs */}
          <div className="flex items-center bg-stone-100 dark:bg-stone-700 rounded-lg p-1">
            <button
              onClick={() => setMode('transcription')}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                mode === 'transcription'
                  ? 'bg-white dark:bg-stone-600 text-stone-900 dark:text-stone-100 shadow-sm'
                  : 'text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-200'
              }`}
            >
              语音识别
            </button>
            <button
              onClick={() => setMode('tts')}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                mode === 'tts'
                  ? 'bg-white dark:bg-stone-600 text-stone-900 dark:text-stone-100 shadow-sm'
                  : 'text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-200'
              }`}
            >
              文字转语音
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Input Panel */}
        <div className="w-1/2 flex flex-col border-r border-stone-200 dark:border-stone-700">
          <div className="p-4 space-y-4 flex-1 overflow-y-auto">
            {/* Model Selection */}
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  模型配置
                </label>
                <select
                  value={selectedProfileId}
                  onChange={(e) => handleProfileChange(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                >
                  <option value="">选择配置...</option>
                  {profiles?.map(profile => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              </div>

              {selectedProfileId && (
                <div>
                  <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                    模型
                  </label>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                  >
                    {profiles
                      ?.find(p => p.id === selectedProfileId)
                      ?.available_models.map(model => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))}
                  </select>
                </div>
              )}
            </div>

            {mode === 'transcription' ? (
              <>
                {/* File Upload */}
                <div>
                  <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                    音频文件
                  </label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="audio/*"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  {selectedFile ? (
                    <div className="flex items-center gap-3 p-3 bg-stone-100 dark:bg-stone-700 rounded-lg">
                      <FileAudio className="w-8 h-8 text-stone-500" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-stone-900 dark:text-stone-100 truncate">
                          {selectedFile.name}
                        </p>
                        <p className="text-xs text-stone-500">
                          {formatFileSize(selectedFile.size)}
                        </p>
                      </div>
                      <button
                        onClick={() => setSelectedFile(null)}
                        className="p-1 hover:bg-stone-200 dark:hover:bg-stone-600 rounded"
                      >
                        <X className="w-4 h-4 text-stone-500" />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="w-full flex flex-col items-center gap-2 p-6 border-2 border-dashed border-stone-300 dark:border-stone-600 rounded-lg hover:border-teal-500 hover:bg-teal-50/50 dark:hover:bg-teal-900/10 transition-colors"
                    >
                      <Upload className="w-8 h-8 text-stone-400" />
                      <span className="text-sm text-stone-600 dark:text-stone-400">
                        点击上传音频文件
                      </span>
                      <span className="text-xs text-stone-400">
                        支持 mp3, wav, m4a, ogg 等格式
                      </span>
                    </button>
                  )}
                </div>

                {/* Language */}
                <div>
                  <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                    语言
                  </label>
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
                  >
                    {LANGUAGES.map(lang => (
                      <option key={lang.code} value={lang.code}>
                        {lang.label}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            ) : (
              <>
                {/* TTS Text Input */}
                <div>
                  <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                    输入文本
                  </label>
                  <textarea
                    value={ttsText}
                    onChange={(e) => setTtsText(e.target.value)}
                    placeholder="输入要转换为语音的文本..."
                    rows={6}
                    className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 resize-none"
                  />
                </div>

                {/* Voice Selection */}
                <div>
                  <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                    声音
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {TTS_VOICES.map(v => (
                      <button
                        key={v}
                        onClick={() => setVoice(v)}
                        className={`px-3 py-2 text-sm rounded-lg border transition-colors ${
                          voice === v
                            ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300'
                            : 'border-stone-300 dark:border-stone-600 hover:border-stone-400 text-stone-700 dark:text-stone-300'
                        }`}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Speed */}
                <div>
                  <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                    语速: {speed}x
                  </label>
                  <input
                    type="range"
                    min={0.25}
                    max={4}
                    step={0.25}
                    value={speed}
                    onChange={(e) => setSpeed(parseFloat(e.target.value))}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-stone-400 mt-1">
                    <span>0.25x</span>
                    <span>4x</span>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Submit Button */}
          <div className="p-4 border-t border-stone-200 dark:border-stone-700">
            <button
              onClick={() => mode === 'transcription' ? transcriptionMutation.mutate() : ttsMutation.mutate()}
              disabled={
                mode === 'transcription'
                  ? !canTranscribe || transcriptionMutation.isPending
                  : !canGenerateSpeech || ttsMutation.isPending
              }
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed"
            >
              {(transcriptionMutation.isPending || ttsMutation.isPending) ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  处理中...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  {mode === 'transcription' ? '开始识别' : '生成语音'}
                </>
              )}
            </button>
          </div>
        </div>

        {/* Result Panel */}
        <div className="w-1/2 flex flex-col bg-stone-50 dark:bg-stone-900/50">
          <div className="px-4 py-3 border-b border-stone-200 dark:border-stone-700">
            <span className="text-sm font-medium text-stone-700 dark:text-stone-300">
              {mode === 'transcription' ? '识别结果' : '生成结果'}
            </span>
          </div>

          <div className="flex-1 p-4 overflow-y-auto">
            {mode === 'transcription' ? (
              transcriptionMutation.error ? (
                <div className="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-red-700 dark:text-red-400">
                      识别失败
                    </p>
                    <p className="text-sm text-red-600 dark:text-red-300 mt-1">
                      {(transcriptionMutation.error as any)?.response?.data?.detail ||
                        (transcriptionMutation.error as Error).message}
                    </p>
                  </div>
                </div>
              ) : transcriptionResult ? (
                <div className="space-y-4">
                  {/* Metadata */}
                  <div className="grid grid-cols-2 gap-3">
                    {transcriptionResult.language && (
                      <div className="p-3 bg-white dark:bg-stone-800 rounded-lg">
                        <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
                          检测语言
                        </div>
                        <div className="text-sm font-medium text-stone-900 dark:text-stone-100">
                          {transcriptionResult.language}
                        </div>
                      </div>
                    )}
                    {transcriptionResult.duration && (
                      <div className="p-3 bg-white dark:bg-stone-800 rounded-lg">
                        <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
                          时长
                        </div>
                        <div className="text-sm font-medium text-stone-900 dark:text-stone-100">
                          {formatDuration(transcriptionResult.duration)}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Transcription Text */}
                  <div>
                    <div className="text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                      识别文本
                    </div>
                    <div className="p-4 bg-white dark:bg-stone-800 rounded-lg">
                      <p className="text-stone-700 dark:text-stone-300 whitespace-pre-wrap">
                        {transcriptionResult.text}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-stone-500 dark:text-stone-400">
                  <div className="text-center">
                    <Mic className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p className="text-sm">上传音频文件并开始识别</p>
                  </div>
                </div>
              )
            ) : (
              // TTS Results
              ttsMutation.error ? (
                <div className="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-red-700 dark:text-red-400">
                      生成失败
                    </p>
                    <p className="text-sm text-red-600 dark:text-red-300 mt-1">
                      {(ttsMutation.error as any)?.response?.data?.detail ||
                        (ttsMutation.error as Error).message}
                    </p>
                  </div>
                </div>
              ) : audioBlob ? (
                <div className="space-y-4">
                  {/* Audio Player */}
                  <div className="p-4 bg-white dark:bg-stone-800 rounded-lg">
                    <div className="flex items-center gap-4">
                      <button
                        onClick={handlePlayPause}
                        className="w-12 h-12 rounded-full bg-teal-600 hover:bg-teal-700 text-white flex items-center justify-center transition-colors"
                      >
                        {isPlaying ? (
                          <Pause className="w-5 h-5" />
                        ) : (
                          <Play className="w-5 h-5 ml-0.5" />
                        )}
                      </button>
                      <div className="flex-1">
                        <div className="text-sm font-medium text-stone-900 dark:text-stone-100">
                          生成的语音
                        </div>
                        <div className="text-xs text-stone-500 dark:text-stone-400">
                          声音: {voice} · 语速: {speed}x · {formatFileSize(audioBlob.size)}
                        </div>
                      </div>
                      <button
                        onClick={handleDownloadAudio}
                        className="p-2 hover:bg-stone-100 dark:hover:bg-stone-700 rounded-lg transition-colors"
                      >
                        <Download className="w-5 h-5 text-stone-500" />
                      </button>
                    </div>
                    <audio
                      ref={audioRef}
                      onEnded={() => setIsPlaying(false)}
                      className="hidden"
                    />
                  </div>

                  {/* Original Text */}
                  <div>
                    <div className="text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                      原始文本
                    </div>
                    <div className="p-3 bg-white dark:bg-stone-800 rounded-lg text-sm text-stone-600 dark:text-stone-400">
                      {ttsText}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-stone-500 dark:text-stone-400">
                  <div className="text-center">
                    <Volume2 className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p className="text-sm">输入文本并生成语音</p>
                  </div>
                </div>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
