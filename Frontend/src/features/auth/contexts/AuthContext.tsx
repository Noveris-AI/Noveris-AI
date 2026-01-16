import { createContext, useContext, useState, useEffect, useMemo, useCallback, ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { authClient } from '../api/authClient'
import { apiClient } from '@/shared/lib/apiClient'
import type { User, LoginRequest } from '../api/authTypes'

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: Error | null
  login: (credentials: LoginRequest) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [shouldCheckAuth, setShouldCheckAuth] = useState(false)

  // Query for current user
  const {
    data: user,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['currentUser'],
    queryFn: () => authClient.getCurrentUser(),
    enabled: shouldCheckAuth,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false, // Don't retry on 401
    refetchOnWindowFocus: true, // Refetch when window regains focus - enables multi-tab sync
    refetchOnReconnect: true, // Refetch when network reconnects
  })

  // Register global 401 unauthorized handler
  useEffect(() => {
    apiClient.onUnauthorized = () => {
      // Clear auth state
      setShouldCheckAuth(false)
      queryClient.clear()

      // Redirect to login page
      navigate('/auth/login', { replace: true })
    }

    return () => {
      apiClient.onUnauthorized = undefined
    }
  }, [navigate, queryClient])

  const login = useCallback(async (credentials: LoginRequest) => {
    await authClient.login(credentials)

    // Enable auth check and invalidate current user query
    setShouldCheckAuth(true)
    queryClient.invalidateQueries({ queryKey: ['currentUser'] })
  }, [queryClient])

  const logout = useCallback(async () => {
    try {
      await authClient.logout()
    } catch (error) {
      // Ignore logout errors (session might already be expired)
      console.warn('Logout request failed:', error)
    } finally {
      // Clear auth state regardless of logout success
      setShouldCheckAuth(false)
      queryClient.clear()
    }
  }, [queryClient])

  const checkAuth = useCallback(() => {
    setShouldCheckAuth(true)
  }, [])

  const value = useMemo(
    () => ({
      user: user ?? null,
      isAuthenticated: !!user,
      isLoading,
      error: error as Error | null,
      login,
      logout,
      checkAuth,
    }),
    [user, isLoading, error, login, logout, checkAuth]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuthContext() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuthContext must be used within AuthProvider')
  }
  return context
}
