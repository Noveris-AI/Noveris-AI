import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@/shared/components/theme/ThemeProvider'
import LoginPage from '../pages/LoginPage'
import { expect, describe, it, vi, beforeEach } from 'vitest'

// Mock i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'auth.login.title': '登录您的账户',
        'auth.login.subtitle': '输入您的凭据以访问您的账户',
        'auth.login.email.label': '邮箱地址',
        'auth.login.email.placeholder': '请输入邮箱地址',
        'auth.login.email.required': '请输入邮箱地址',
        'auth.login.password.label': '密码',
        'auth.login.password.placeholder': '请输入密码',
        'auth.login.password.required': '请输入密码',
        'auth.login.password.toggleVisibility': '切换密码可见性',
        'auth.login.rememberMe.label': '记住我',
        'auth.login.forgotPassword.link': '忘记密码？',
        'auth.login.submit': '登录',
        'auth.login.loading': '登录中...',
        'auth.login.error.invalid': '邮箱或密码错误',
        'auth.login.error.general': '登录失败，请稍后重试',
        'auth.login.noAccount': '还没有账户？',
        'auth.login.signUp': '注册',
      }
      return translations[key] || key
    },
  }),
}))

// Mock auth client
vi.mock('../api/authClient', () => ({
  authClient: {
    login: vi.fn(),
  },
}))

// Mock navigation
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock auth navigation
vi.mock('../hooks/useAuthNavigation', () => ({
  useAuthNavigation: () => ({
    goToLogin: vi.fn(),
    goToRegister: vi.fn(),
    goToForgotPassword: vi.fn(),
    goToResetPassword: vi.fn(),
    goToHome: vi.fn(),
  }),
}))

import { authClient } from '../api/authClient'
import { useAuthNavigation } from '../hooks/useAuthNavigation'

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
    mutations: {
      retry: false,
    },
  },
})

const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={createTestQueryClient()}>
    <ThemeProvider>
      <BrowserRouter>
        {children}
      </BrowserRouter>
    </ThemeProvider>
  </QueryClientProvider>
)

describe('Login Form', () => {
  const mockAuthClient = vi.mocked(authClient)
  const mockAuthNavigation = vi.mocked(useAuthNavigation())

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders login form correctly', () => {
    render(
      <TestWrapper>
        <LoginPage />
      </TestWrapper>
    )

    expect(screen.getByText('登录您的账户')).toBeInTheDocument()
    expect(screen.getByText('输入您的凭据以访问您的账户')).toBeInTheDocument()
    expect(screen.getByLabelText('邮箱地址')).toBeInTheDocument()
    expect(screen.getByLabelText('密码')).toBeInTheDocument()
    expect(screen.getByLabelText('记住我')).toBeInTheDocument()
    expect(screen.getByText('忘记密码？')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument()
  })

  it('shows validation errors for empty form submission', async () => {
    const user = userEvent.setup()

    render(
      <TestWrapper>
        <LoginPage />
      </TestWrapper>
    )

    const submitButton = screen.getByRole('button', { name: '登录' })
    await user.click(submitButton)

    expect(await screen.findByText('请输入邮箱地址')).toBeInTheDocument()
    expect(screen.getByText('请输入密码')).toBeInTheDocument()
  })

  it('toggles password visibility', async () => {
    const user = userEvent.setup()

    render(
      <TestWrapper>
        <LoginPage />
      </TestWrapper>
    )

    const passwordInput = screen.getByLabelText('密码')
    const toggleButton = screen.getByLabelText('切换密码可见性')

    // 初始状态应该是password类型
    expect(passwordInput).toHaveAttribute('type', 'password')

    // 点击切换
    await user.click(toggleButton)
    expect(passwordInput).toHaveAttribute('type', 'text')

    // 再次点击
    await user.click(toggleButton)
    expect(passwordInput).toHaveAttribute('type', 'password')
  })

  it('submits form and shows loading state', async () => {
    const user = userEvent.setup()

    mockAuthClient.login.mockImplementation(() =>
      new Promise(resolve => setTimeout(() => resolve({ success: true }), 100))
    )

    render(
      <TestWrapper>
        <LoginPage />
      </TestWrapper>
    )

    const emailInput = screen.getByLabelText('邮箱地址')
    const passwordInput = screen.getByLabelText('密码')
    const submitButton = screen.getByRole('button', { name: '登录' })

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'password123')
    await user.click(submitButton)

    // 检查按钮显示loading状态
    expect(screen.getByRole('button', { name: '登录中...' })).toBeInTheDocument()

    // 等待提交完成
    await waitFor(() => {
      expect(mockAuthClient.login).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
        rememberMe: false,
      })
    })
  })

  it('shows error message on login failure', async () => {
    const user = userEvent.setup()

    mockAuthClient.login.mockRejectedValue({
      code: 'INVALID_CREDENTIALS',
      message: 'Invalid credentials',
    })

    render(
      <TestWrapper>
        <LoginPage />
      </TestWrapper>
    )

    const emailInput = screen.getByLabelText('邮箱地址')
    const passwordInput = screen.getByLabelText('密码')
    const submitButton = screen.getByRole('button', { name: '登录' })

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'wrongpassword')
    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText('邮箱或密码错误')).toBeInTheDocument()
    })
  })

  it('navigates to home on successful login', async () => {
    const user = userEvent.setup()

    mockAuthClient.login.mockResolvedValue({
      success: true,
      user: { id: '1', email: 'test@example.com', name: 'Test User' },
      redirectTo: '/',
    })

    render(
      <TestWrapper>
        <LoginPage />
      </TestWrapper>
    )

    const emailInput = screen.getByLabelText('邮箱地址')
    const passwordInput = screen.getByLabelText('密码')
    const submitButton = screen.getByRole('button', { name: '登录' })

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'password123')
    await user.click(submitButton)

    await waitFor(() => {
      expect(mockAuthNavigation.goToHome).toHaveBeenCalled()
    })
  })
})
