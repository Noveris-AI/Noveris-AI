// Auth API 类型定义

export interface LoginRequest {
  email: string
  password: string
  rememberMe?: boolean
}

export interface RegisterRequest {
  email: string
  verificationCode: string
  password: string
}

export interface SendVerificationCodeRequest {
  email: string
}

export interface ForgotPasswordRequest {
  email: string
}

export interface ResetPasswordRequest {
  token?: string // URL参数中的token
  code?: string  // 用户输入的code
  newPassword: string
}

export interface AuthResponse {
  success: boolean
  message?: string
  data?: any // 用于返回额外数据，如重置链接
}

export interface LoginResponse extends AuthResponse {
  user?: {
    id: string
    email: string
    name: string
  }
  redirectTo?: string
}

export interface User {
  id: string
  email: string
  name: string
}

export interface ChangePasswordRequest {
  currentPassword: string
  newPassword: string
}

export interface SessionInfo {
  id: string
  userAgent?: string
  ipAddress?: string
  createdAt: string
  lastActiveAt: string
}

// API错误类型
export class AuthError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode?: number
  ) {
    super(message)
    this.name = 'AuthError'
  }
}

// AuthClient接口
export interface AuthClient {
  login(data: LoginRequest): Promise<LoginResponse>
  register(data: RegisterRequest): Promise<AuthResponse>
  sendVerificationCode(data: SendVerificationCodeRequest): Promise<AuthResponse>
  forgotPassword(data: ForgotPasswordRequest): Promise<AuthResponse>
  resetPassword(data: ResetPasswordRequest): Promise<AuthResponse>
  logout(): Promise<void>
  getCurrentUser(): Promise<User>
  changePassword(data: ChangePasswordRequest): Promise<AuthResponse>
  getSessions(): Promise<SessionInfo[]>
  revokeSessions(): Promise<AuthResponse>
}
