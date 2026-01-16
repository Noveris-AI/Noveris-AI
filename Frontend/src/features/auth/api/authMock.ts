import { AuthClient, LoginRequest, RegisterRequest, ForgotPasswordRequest, ResetPasswordRequest, SendVerificationCodeRequest, AuthResponse, LoginResponse, AuthError } from './authTypes'
import { AUTH_CONFIG } from '@/shared/config/auth'

// Mock数据存储
const mockUsers = new Map<string, { email: string; password: string; name: string }>()
const mockResetCodes = new Map<string, { code: string; expiresAt: number }>()
const mockVerificationCodes = new Map<string, { code: string; expiresAt: number }>()

// 模拟延迟
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

// 生成随机延迟
const getRandomDelay = () => {
  const { MOCK_DELAY_MIN, MOCK_DELAY_MAX } = AUTH_CONFIG
  return Math.random() * (MOCK_DELAY_MAX - MOCK_DELAY_MIN) + MOCK_DELAY_MIN
}

export class MockAuthClient implements AuthClient {
  async login(data: LoginRequest): Promise<LoginResponse> {
    await delay(getRandomDelay())

    // 检查是否强制失败
    if (AUTH_CONFIG.MOCK_FORCE_FAILURE) {
      throw new AuthError('Invalid email or password', 'INVALID_CREDENTIALS', 401)
    }

    const user = mockUsers.get(data.email)

    if (!user || user.password !== data.password) {
      throw new AuthError('Invalid email or password', 'INVALID_CREDENTIALS', 401)
    }

    return {
      success: true,
      user: {
        id: `user_${Date.now()}`,
        email: user.email,
        name: user.name,
      },
      redirectTo: AUTH_CONFIG.REDIRECT_AFTER_LOGIN,
    }
  }

  async sendVerificationCode(data: SendVerificationCodeRequest): Promise<AuthResponse> {
    await delay(getRandomDelay())

    // 检查是否强制失败
    if (AUTH_CONFIG.MOCK_FORCE_FAILURE) {
      throw new AuthError('Failed to send verification code', 'SEND_CODE_FAILED', 500)
    }

    // 生成6位验证码
    const code = Math.floor(100000 + Math.random() * 900000).toString()
    const expiresAt = Date.now() + (5 * 60 * 1000) // 5分钟后过期

    mockVerificationCodes.set(data.email, { code, expiresAt })

    // 模拟发送成功
    return {
      success: true,
      message: 'Verification code sent',
    }
  }

  async register(data: RegisterRequest): Promise<AuthResponse> {
    await delay(getRandomDelay())

    // 检查是否强制失败
    if (AUTH_CONFIG.MOCK_FORCE_FAILURE) {
      throw new AuthError('Registration failed', 'REGISTRATION_FAILED', 500)
    }

    // 验证验证码
    const verificationData = mockVerificationCodes.get(data.email)
    if (!verificationData || verificationData.expiresAt < Date.now()) {
      throw new AuthError('Verification code expired', 'CODE_EXPIRED', 400)
    }

    if (verificationData.code !== data.verificationCode) {
      throw new AuthError('Invalid verification code', 'INVALID_CODE', 400)
    }

    // 检查邮箱是否已存在
    if (mockUsers.has(data.email)) {
      throw new AuthError('Email already exists', 'EMAIL_EXISTS', 409)
    }

    // 模拟用户注册
    const userName = data.email.split('@')[0] // 简单生成用户名
    mockUsers.set(data.email, {
      email: data.email,
      password: data.password, // 实际应用中应该哈希
      name: userName,
    })

    // 清除验证码
    mockVerificationCodes.delete(data.email)

    return {
      success: true,
      message: 'Registration successful',
    }
  }

  async forgotPassword(data: ForgotPasswordRequest): Promise<AuthResponse> {
    await delay(getRandomDelay())

    // 检查是否强制失败
    if (AUTH_CONFIG.MOCK_FORCE_FAILURE) {
      throw new AuthError('Failed to send reset email', 'SEND_FAILED', 500)
    }

    // 生成重置token (格式: email_timestamp_random)
    const timestamp = Date.now()
    const randomPart = Math.random().toString(36).substring(2, 8)
    const token = `${data.email}_${timestamp}_${randomPart}`
    const expiresAt = timestamp + (15 * 60 * 1000) // 15分钟后过期

    mockResetCodes.set(data.email, { code: token, expiresAt })

    // 生成重置链接
    const resetLink = `${window.location.origin}/auth/reset?token=${encodeURIComponent(token)}`

    console.log('Reset link generated:', resetLink) // 在实际应用中，这里会发送邮件

    // 模拟发送邮件成功（不泄露用户是否存在）
    return {
      success: true,
      message: 'Reset link sent',
      data: {
        resetLink, // 在开发环境下返回链接用于测试
      }
    }
  }

  async resetPassword(data: ResetPasswordRequest): Promise<AuthResponse> {
    await delay(getRandomDelay())

    // 检查是否强制失败
    if (AUTH_CONFIG.MOCK_FORCE_FAILURE) {
      throw new AuthError('Reset failed', 'RESET_FAILED', 500)
    }

    let email: string | null = null

    // 检查token模式
    if (data.token) {
      // 验证token格式: email_timestamp_random
      try {
        const parts = data.token.split('_')
        if (parts.length !== 3) {
          throw new AuthError('Invalid reset token format', 'INVALID_TOKEN', 400)
        }

        const [tokenEmail, timestampStr] = parts
        const timestamp = parseInt(timestampStr)

        // 检查token是否过期
        if (Date.now() > timestamp + (15 * 60 * 1000)) {
          throw new AuthError('Reset token expired', 'TOKEN_EXPIRED', 400)
        }

        // 验证token是否存在于存储中
        const storedTokenData = mockResetCodes.get(tokenEmail)
        if (!storedTokenData || storedTokenData.code !== data.token) {
          throw new AuthError('Invalid reset token', 'INVALID_TOKEN', 400)
        }

        email = tokenEmail
      } catch (error) {
        if (error instanceof AuthError) {
          throw error
        }
        throw new AuthError('Invalid reset token', 'INVALID_TOKEN', 400)
      }
    }

    // 检查code模式（备用）
    if (data.code && !email) {
      // 查找对应的email（简化处理）
      for (const [userEmail, resetData] of mockResetCodes.entries()) {
        if (resetData.code === data.code && resetData.expiresAt > Date.now()) {
          email = userEmail
          break
        }
      }
    }

    if (!email) {
      throw new AuthError('Invalid reset code or token', 'INVALID_CODE', 400)
    }

    const resetData = mockResetCodes.get(email)
    if (!resetData || resetData.expiresAt < Date.now()) {
      throw new AuthError('Reset code expired', 'CODE_EXPIRED', 400)
    }

    // 验证code（如果提供）
    if (data.code && resetData.code !== data.code) {
      throw new AuthError('Invalid reset code', 'INVALID_CODE', 400)
    }

    // 更新用户密码
    const user = mockUsers.get(email)
    if (user) {
      user.password = data.newPassword // 实际应用中应该哈希
    }

    // 清除重置码
    mockResetCodes.delete(email)

    return {
      success: true,
      message: 'Password reset successful',
    }
  }
}
