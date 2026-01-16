import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/shared/components/theme/ThemeProvider'
import App from '@/App'
import { expect, describe, it } from 'vitest'

// 创建测试用的QueryClient
const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
})

// 包装器组件
const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={createTestQueryClient()}>
    <ThemeProvider>
      <BrowserRouter>
        {children}
      </BrowserRouter>
    </ThemeProvider>
  </QueryClientProvider>
)

describe('Auth Routes', () => {
  it('renders login page on /auth/login', async () => {
    window.history.pushState({}, '', '/auth/login')

    render(
      <TestWrapper>
        <App />
      </TestWrapper>
    )

    // 检查页面标题
    expect(await screen.findByText('登录您的账户')).toBeInTheDocument()
    expect(screen.getByText('输入您的凭据以访问您的账户')).toBeInTheDocument()
  })

  it('renders register page on /auth/register', async () => {
    window.history.pushState({}, '', '/auth/register')

    render(
      <TestWrapper>
        <App />
      </TestWrapper>
    )

    // 检查页面标题
    expect(await screen.findByText('创建新账户')).toBeInTheDocument()
    expect(screen.getByText('填写信息以创建您的账户')).toBeInTheDocument()
  })

  it('renders forgot password page on /auth/forgot', async () => {
    window.history.pushState({}, '', '/auth/forgot')

    render(
      <TestWrapper>
        <App />
      </TestWrapper>
    )

    // 检查页面标题
    expect(await screen.findByText('Forgot Password')).toBeInTheDocument()
    expect(screen.getByText('Enter your email address and we\'ll send you instructions to reset your password')).toBeInTheDocument()
  })

  it('renders reset password page on /auth/reset', async () => {
    window.history.pushState({}, '', '/auth/reset?token=test123')

    render(
      <TestWrapper>
        <App />
      </TestWrapper>
    )

    // 检查页面标题
    expect(await screen.findByText('Reset Password')).toBeInTheDocument()
    expect(screen.getByText('Please set a new password to complete the reset.')).toBeInTheDocument()
  })

  it('renders reset password page on /auth/reset', async () => {
    window.history.pushState({}, '', '/auth/reset')

    render(
      <TestWrapper>
        <App />
      </TestWrapper>
    )

    // 检查页面标题
    expect(await screen.findByText('重置密码')).toBeInTheDocument()
    expect(screen.getByText('请输入您的新密码')).toBeInTheDocument()
  })

  it('renders home page on /', () => {
    window.history.pushState({}, '', '/')

    render(
      <TestWrapper>
        <App />
      </TestWrapper>
    )

    // 检查首页内容
    expect(screen.getByText('Noveris AI')).toBeInTheDocument()
    expect(screen.getByText('Welcome to Noveris AI Platform')).toBeInTheDocument()
  })
})
