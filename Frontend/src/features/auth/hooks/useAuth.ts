import { useAuthContext } from '../contexts/AuthContext'

/**
 * Hook to access authentication context
 *
 * @example
 * const { user, isAuthenticated, login, logout } = useAuth()
 *
 * if (!isAuthenticated) {
 *   return <LoginPage />
 * }
 *
 * return <div>Welcome, {user.name}!</div>
 */
export function useAuth() {
  return useAuthContext()
}
