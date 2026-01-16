import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useTranslation } from 'react-i18next'
import { useMutation } from '@tanstack/react-query'
import { AuthCard } from '../components/AuthCard'
import { useAuthNavigation } from '../hooks/useAuthNavigation'
import { authClient } from '../api/authClient'
import { forgotPasswordSchema, ForgotPasswordFormData } from '../validation/schemas'
import { Input } from '@/shared/components/ui/Input'
import { Label } from '@/shared/components/ui/Label'
import { Button } from '@/shared/components/ui/Button'

const ForgotPasswordPage = () => {
  const { t, ready } = useTranslation('translation')

  const { goToLogin } = useAuthNavigation()
  const [isSuccess, setIsSuccess] = useState(false)
  const [countdown, setCountdown] = useState(0)


  const {
    register,
    handleSubmit,
    formState: { errors },
    setError,
  } = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
  })

  // 倒计时效果
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [countdown])

  const forgotPasswordMutation = useMutation({
    mutationFn: authClient.forgotPassword,
    onSuccess: (response) => {
      if (response.success) {
        setIsSuccess(true)
        setCountdown(60) // 60秒倒计时

        // 在开发环境下显示生成的resetLink
        if (response.data?.resetLink) {
          console.log('🔗 Reset Link (for testing):', response.data.resetLink)
        }
      }
    },
    onError: () => {
      setError('root', {
        message: ready ? t('auth.forgotPasswordPage.error.general') : '发送失败，请稍后重试',
      })
    },
  })

  const onSubmit = (data: ForgotPasswordFormData) => {
    forgotPasswordMutation.mutate(data)
  }

  if (isSuccess) {
    return (
      <AuthCard
        title={t('auth.forgotPasswordPage.title')}
        footer={
          <div className="text-center space-y-2">
            <button
              onClick={goToLogin}
              className="text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 font-medium transition-colors duration-200"
            >
              {ready ? t('auth.forgotPasswordPage.actions.backToLogin') : '返回登录'}
            </button>
            <p className="text-xs text-stone-600 dark:text-stone-400">
              {ready ? t('auth.forgotPasswordPage.notice.ssoHint') : '若您的组织使用 SSO 登录，请通过身份提供方重置密码或联系管理员。'}
            </p>
          </div>
        }
      >
        <div className="space-y-4">
          {/* 成功提示 - 企业级Alert样式 */}
          <div className="p-4 bg-teal-50 dark:bg-teal-900/20 border border-teal-200 dark:border-teal-800 rounded-lg">
            <div className="flex items-start gap-3">
              <svg className="w-5 h-5 text-teal-600 dark:text-teal-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <div className="space-y-2">
                <p className="text-sm text-teal-800 dark:text-teal-200 font-medium">
                  {ready ? t('auth.forgotPasswordPage.notice.success') : '如果该邮箱已注册，我们将发送重置指引至您的邮箱。'}
                </p>
                <p className="text-xs text-teal-700 dark:text-teal-300">
                  {ready ? t('auth.forgotPasswordPage.notice.checkSpam') : '请检查您的邮箱，包括垃圾邮件文件夹。'}
                </p>
              </div>
            </div>
          </div>

          {/* 重新发送按钮 */}
          <div className="text-center">
            <button
              onClick={() => {
                setIsSuccess(false)
                setCountdown(0)
              }}
              disabled={countdown > 0}
              className="text-sm text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 font-medium disabled:text-stone-400 dark:disabled:text-stone-600 disabled:cursor-not-allowed transition-colors duration-200"
            >
              {countdown > 0
                ? (ready ? t('auth.forgotPasswordPage.actions.resendCountdown', { seconds: countdown }) : `重新发送 (${countdown}s)`)
                : (ready ? t('auth.forgotPasswordPage.actions.resend') : '重新发送')
              }
            </button>
          </div>
        </div>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title={ready ? t('auth.forgotPasswordPage.title') : '忘记密码'}
      subtitle={ready ? t('auth.forgotPasswordPage.subtitle') : '输入您的邮箱地址，我们将向您发送重置密码的指引'}
        footer={
          <div className="text-center space-y-2">
            <button
              onClick={goToLogin}
              className="text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 font-medium transition-colors duration-200"
            >
              {ready ? t('auth.forgotPasswordPage.actions.backToLogin') : '返回登录'}
            </button>
            <p className="text-xs text-stone-600 dark:text-stone-400">
              {ready ? t('auth.forgotPasswordPage.notice.ssoHint') : '若您的组织使用 SSO 登录，请通过身份提供方重置密码或联系管理员。'}
            </p>
          </div>
        }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3.5">
        {/* 邮箱字段 */}
        <div className="space-y-1">
          <Label htmlFor="email" className="text-xs font-medium">
            {ready ? t('auth.forgotPasswordPage.email.label') : '邮箱地址'}
          </Label>
          <Input
            {...register('email')}
            id="email"
            type="email"
            placeholder={ready ? t('auth.forgotPasswordPage.email.placeholder') : '请输入您的邮箱地址'}
            className={errors.email ? 'border-red-500 focus-visible:ring-red-500' : ''}
          />
          {errors.email && (
            <p className="text-[11px] text-red-600 dark:text-red-400 mt-1 leading-4">
              {t(errors.email.message || 'common.error')}
            </p>
          )}
        </div>


        {/* 全局错误信息 */}
        {errors.root && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-[11px] text-red-600 dark:text-red-400 leading-4">
              {errors.root.message}
            </p>
          </div>
        )}

        {/* 提交按钮 */}
        <Button
          type="submit"
          disabled={forgotPasswordMutation.isPending || countdown > 0}
          className="w-full mt-3 text-sm"
        >
          {forgotPasswordMutation.isPending
            ? (ready ? t('auth.forgotPasswordPage.loading') : '发送中...')
            : countdown > 0
            ? (ready ? t('auth.forgotPasswordPage.actions.resendCountdown', { seconds: countdown }) : `重新发送 (${countdown}s)`)
            : (ready ? t('auth.forgotPasswordPage.actions.send') : '发送重置指引')
          }
        </Button>
      </form>
    </AuthCard>
  )
}

export default ForgotPasswordPage
