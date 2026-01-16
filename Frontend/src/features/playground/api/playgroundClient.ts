/**
 * Playground API Client
 *
 * Handles all playground-related API calls.
 * Uses shared API configuration for consistent base URL handling.
 */

import axios from 'axios'
import { API_CONFIG } from '@shared/config/api'

const API_BASE = API_CONFIG.BASE_URL

// Types
export interface EmbeddingRequest {
  input: string | string[]
  model: string
  model_profile_id?: string
}

export interface EmbeddingResponse {
  object: string
  data: Array<{
    object: string
    embedding: number[]
    index: number
  }>
  model: string
  usage: {
    prompt_tokens: number
    total_tokens: number
  }
}

export interface RerankRequest {
  query: string
  documents: string[]
  model: string
  model_profile_id?: string
  top_n?: number
}

export interface RerankResult {
  index: number
  document: string
  relevance_score: number
}

export interface RerankResponse {
  model: string
  results: RerankResult[]
  usage?: {
    prompt_tokens: number
    total_tokens: number
  }
}

export interface ImageGenerationRequest {
  prompt: string
  model: string
  model_profile_id?: string
  n?: number
  size?: string
  quality?: string
  style?: string
}

export interface ImageResult {
  url?: string
  b64_json?: string
  revised_prompt?: string
}

export interface ImageGenerationResponse {
  created: number
  data: ImageResult[]
}

export interface AudioTranscriptionRequest {
  file: File
  model: string
  model_profile_id?: string
  language?: string
  response_format?: string
}

export interface AudioTranscriptionResponse {
  text: string
  language?: string
  duration?: number
  words?: Array<{
    word: string
    start: number
    end: number
  }>
}

export interface TextToSpeechRequest {
  input: string
  model: string
  model_profile_id?: string
  voice?: string
  speed?: number
  response_format?: string
}

// API Client
class PlaygroundClient {
  // Embeddings
  async createEmbedding(request: EmbeddingRequest): Promise<EmbeddingResponse> {
    const response = await axios.post(`${API_BASE}/api/playground/embeddings`, request)
    return response.data
  }

  // Rerank
  async rerank(request: RerankRequest): Promise<RerankResponse> {
    const response = await axios.post(`${API_BASE}/api/playground/rerank`, request)
    return response.data
  }

  // Image Generation
  async generateImage(request: ImageGenerationRequest): Promise<ImageGenerationResponse> {
    const response = await axios.post(`${API_BASE}/api/playground/images/generations`, request)
    return response.data
  }

  // Audio Transcription
  async transcribeAudio(request: AudioTranscriptionRequest): Promise<AudioTranscriptionResponse> {
    const formData = new FormData()
    formData.append('file', request.file)
    formData.append('model', request.model)
    if (request.model_profile_id) formData.append('model_profile_id', request.model_profile_id)
    if (request.language) formData.append('language', request.language)
    if (request.response_format) formData.append('response_format', request.response_format)

    const response = await axios.post(
      `${API_BASE}/api/playground/audio/transcriptions`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return response.data
  }

  // Text to Speech
  async textToSpeech(request: TextToSpeechRequest): Promise<Blob> {
    const response = await axios.post(
      `${API_BASE}/api/playground/audio/speech`,
      request,
      { responseType: 'blob' }
    )
    return response.data
  }

  // Get available models by capability
  async getModels(capability: string): Promise<Array<{ profile_id: string; profile_name: string; models: string[] }>> {
    const response = await axios.get(`${API_BASE}/api/playground/models`, {
      params: { capability }
    })
    return response.data
  }
}

export const playgroundClient = new PlaygroundClient()
