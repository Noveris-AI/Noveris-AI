import { useNavigate } from 'react-router-dom'
import { AUTH_CONFIG } from '@/shared/config/auth'

export const useAuthNavigation = () => {
  const navigate = useNavigate()

  const goToLogin = () => navigate('/auth/login')
  const goToRegister = () => navigate('/auth/register')
  const goToForgotPassword = () => navigate('/auth/forgot')
  const goToResetPassword = (token?: string) => {
    const path = token ? `/auth/reset?token=${token}` : '/auth/reset'
    navigate(path)
  }

  const goToHome = () => navigate(AUTH_CONFIG.REDIRECT_AFTER_LOGIN)

  return {
    goToLogin,
    goToRegister,
    goToForgotPassword,
    goToResetPassword,
    goToHome,
  }
}
