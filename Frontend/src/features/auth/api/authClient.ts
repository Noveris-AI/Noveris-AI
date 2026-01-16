import { AuthClient } from './authTypes'
import { MockAuthClient } from './authMock'
import { RealAuthClient } from './authReal'
import { AUTH_CONFIG } from '@/shared/config/auth'

// 创建客户端实例
const _createAuthClient = (): AuthClient => {
  if (AUTH_CONFIG.API_MODE === 'mock') {
    return new MockAuthClient()
  }

  return new RealAuthClient()
}

// 创建实例并绑定所有方法
const clientInstance = _createAuthClient()

// 导出绑定后的方法，确保 'this' 上下文正确
export const authClient: AuthClient = {
  login: (data) => clientInstance.login(data),
  register: (data) => clientInstance.register(data),
  sendVerificationCode: (data) => clientInstance.sendVerificationCode(data),
  forgotPassword: (data) => clientInstance.forgotPassword(data),
  resetPassword: (data) => clientInstance.resetPassword(data),
}

// 保留创建函数供需要时使用
export const createAuthClient = _createAuthClient
