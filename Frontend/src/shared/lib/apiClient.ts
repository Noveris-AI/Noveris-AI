/**
 * Base API Client
 *
 * Shared HTTP client with common functionality for all API services.
 * Features: error handling, retry logic, request/response interceptors.
 */

import { API_CONFIG } from '@shared/config/api'

// Error types
export class ApiError extends Error {
  public readonly status: number
  public readonly code?: string
  public readonly details?: Record<string, unknown>

  constructor(
    message: string,
    status: number,
    code?: string,
    details?: Record<string, unknown>
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export class NetworkError extends Error {
  constructor(message: string = 'Network error occurred') {
    super(message)
    this.name = 'NetworkError'
  }
}

export class TimeoutError extends Error {
  constructor(message: string = 'Request timed out') {
    super(message)
    this.name = 'TimeoutError'
  }
}

// Response types
export interface ApiResponse<T> {
  data: T
  status: number
  headers: Headers
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface PaginationParams {
  limit?: number
  offset?: number
  page?: number
  page_size?: number
}

// Request options
export interface RequestOptions extends Omit<RequestInit, 'body'> {
  timeout?: number
  retries?: number
  params?: Record<string, string | number | boolean | undefined>
  body?: unknown
}

/**
 * Base API Client class
 */
export class BaseApiClient {
  protected readonly baseUrl: string
  protected readonly defaultTimeout: number
  public onUnauthorized?: () => void

  constructor(basePath: string = '') {
    this.baseUrl = `${API_CONFIG.BASE_URL}${API_CONFIG.API_VERSION}${basePath}`
    this.defaultTimeout = API_CONFIG.TIMEOUT
  }

  /**
   * Build URL with query parameters
   */
  protected buildUrl(endpoint: string, params?: Record<string, string | number | boolean | undefined>): string {
    let url = `${this.baseUrl}${endpoint}`

    if (params) {
      const searchParams = new URLSearchParams()
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          searchParams.append(key, String(value))
        }
      })
      const queryString = searchParams.toString()
      if (queryString) {
        url += `?${queryString}`
      }
    }

    return url
  }

  /**
   * Get authentication headers
   * Authentication is now handled via session cookies
   */
  protected getAuthHeaders(): Record<string, string> {
    const headers: Record<string, string> = {}

    // Authentication is handled via HttpOnly cookies
    // No need to manually add auth headers

    return headers
  }

  /**
   * Make HTTP request with retry logic and error handling
   */
  protected async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const {
      timeout = this.defaultTimeout,
      retries = 0,
      params,
      body,
      ...fetchOptions
    } = options

    const url = this.buildUrl(endpoint, params)

    const requestInit: RequestInit = {
      ...fetchOptions,
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
        ...fetchOptions.headers,
      },
      credentials: 'include',
    }

    if (body !== undefined) {
      requestInit.body = JSON.stringify(body)
    }

    // Create abort controller for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)
    requestInit.signal = controller.signal

    let lastError: Error | null = null

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const response = await fetch(url, requestInit)
        clearTimeout(timeoutId)

        // Handle different status codes
        if (response.status === 204) {
          return {} as T
        }

        // Handle unauthorized (401) - trigger global unauthorized callback
        if (response.status === 401) {
          this.onUnauthorized?.()
          throw new ApiError(
            'Unauthorized - please login again',
            401,
            'UNAUTHORIZED'
          )
        }

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new ApiError(
            errorData.detail || errorData.message || `Request failed with status ${response.status}`,
            response.status,
            errorData.code,
            errorData.details
          )
        }

        return await response.json()
      } catch (error) {
        clearTimeout(timeoutId)

        if (error instanceof ApiError) {
          // Don't retry client errors (4xx)
          if (error.status >= 400 && error.status < 500) {
            throw error
          }
        }

        if (error instanceof Error) {
          if (error.name === 'AbortError') {
            lastError = new TimeoutError()
          } else if (error instanceof TypeError) {
            lastError = new NetworkError(error.message)
          } else {
            lastError = error
          }
        }

        // If we have more retries, wait before retrying
        if (attempt < retries) {
          const delay = API_CONFIG.RETRY.RETRY_DELAY * Math.pow(API_CONFIG.RETRY.RETRY_MULTIPLIER, attempt)
          await new Promise(resolve => setTimeout(resolve, delay))
        }
      }
    }

    throw lastError || new Error('Request failed')
  }

  /**
   * GET request
   */
  protected get<T>(endpoint: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET', params })
  }

  /**
   * POST request
   */
  protected post<T>(endpoint: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
    return this.request<T>(endpoint, { method: 'POST', body, params })
  }

  /**
   * PUT request
   */
  protected put<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, { method: 'PUT', body })
  }

  /**
   * PATCH request
   */
  protected patch<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, { method: 'PATCH', body })
  }

  /**
   * DELETE request
   */
  protected delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }
}

// Create and export a global API client instance
export const apiClient = new BaseApiClient()

export default BaseApiClient
