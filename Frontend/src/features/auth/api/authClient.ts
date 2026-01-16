import { AuthClient } from './authTypes'
import { RealAuthClient } from './authReal'

// Create real auth client instance
const clientInstance = new RealAuthClient()

// Export bound methods to ensure correct 'this' context
export const authClient: AuthClient = {
  login: (data) => clientInstance.login(data),
  register: (data) => clientInstance.register(data),
  sendVerificationCode: (data) => clientInstance.sendVerificationCode(data),
  forgotPassword: (data) => clientInstance.forgotPassword(data),
  resetPassword: (data) => clientInstance.resetPassword(data),
  logout: () => clientInstance.logout(),
  getCurrentUser: () => clientInstance.getCurrentUser(),
  changePassword: (data) => clientInstance.changePassword(data),
  getSessions: () => clientInstance.getSessions(),
  revokeSessions: () => clientInstance.revokeSessions(),
}
