import { API_CONFIG } from '@shared/config/api'
import {
  AuthClient,
  LoginRequest,
  RegisterRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  SendVerificationCodeRequest,
  AuthResponse,
  LoginResponse,
  AuthError,
} from './authTypes'

class RealAuthClient implements AuthClient {
  private readonly baseUrl: string

  constructor() {
    this.baseUrl = `${API_CONFIG.BASE_URL}${API_CONFIG.API_VERSION}`
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      credentials: 'include', // Send and receive cookies
    })

    const data = await response.json()

    if (!response.ok) {
      throw new AuthError(
        data.error?.message || data.message || data.detail || 'Request failed',
        data.error?.code || 'UNKNOWN_ERROR',
        response.status
      )
    }

    return data
  }

  async login(data: LoginRequest): Promise<LoginResponse> {
    const response = await this.request<{ success: boolean; user?: any; redirect_to?: string; message?: string }>(
      '/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({
          email: data.email,
          password: data.password,
          remember_me: data.rememberMe,
        }),
      }
    )

    return {
      success: response.success || !!response.user,
      user: response.user,
      redirectTo: response.redirect_to,
    }
  }

  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await this.request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email: data.email,
        verification_code: data.verificationCode,
        password: data.password,
      }),
    })

    return response
  }

  async sendVerificationCode(data: SendVerificationCodeRequest): Promise<AuthResponse> {
    const response = await this.request<AuthResponse>('/auth/send-verification-code', {
      method: 'POST',
      body: JSON.stringify({
        email: data.email,
      }),
    })

    return response
  }

  async forgotPassword(data: ForgotPasswordRequest): Promise<AuthResponse> {
    const response = await this.request<AuthResponse>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({
        email: data.email,
      }),
    })

    return response
  }

  async resetPassword(data: ResetPasswordRequest): Promise<AuthResponse> {
    const response = await this.request<AuthResponse>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({
        token: data.token,
        code: data.code,
        new_password: data.newPassword,
      }),
    })

    return response
  }

  async logout(): Promise<void> {
    await this.request<void>('/auth/logout', {
      method: 'POST',
    })
  }

  async getCurrentUser(): Promise<any> {
    return this.request<any>('/auth/me')
  }
}

export { RealAuthClient }
