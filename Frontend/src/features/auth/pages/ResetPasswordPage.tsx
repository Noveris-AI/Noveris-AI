import { useState, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { AuthCard } from '../components/AuthCard'
import { PasswordStrengthHint } from '../components/PasswordStrengthHint'
import { useAuthNavigation } from '../hooks/useAuthNavigation'
import { authClient } from '../api/authClient'
import { resetPasswordSchema, ResetPasswordFormData } from '../validation/schemas'
import { Input } from '@/shared/components/ui/Input'
import { Label } from '@/shared/components/ui/Label'
import { Button } from '@/shared/components/ui/Button'

const ResetPasswordPage = () => {
  const { t, ready } = useTranslation()
  const { goToLogin } = useAuthNavigation()
  const [searchParams] = useSearchParams()
  const [isSuccess, setIsSuccess] = useState(false)
  const [pwdFocused, setPwdFocused] = useState(false)
  const [pwdInteracted, setPwdInteracted] = useState(false)

  const token = searchParams.get('token')
  const hasToken = !!token

  // 根据模式确定标题和副标题
  const title = useMemo(() => t('auth.resetPassword.title'), [t])
  const subtitle = useMemo(() =>
    t(`auth.resetPassword.subtitle.${hasToken ? 'token' : 'code'}`),
    [t, hasToken]
  )

  const {
    register,
    handleSubmit,
    formState: { errors },
    setError,
    watch,
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      code: '',
      newPassword: '',
      confirmPassword: '',
    },
  })


  const resetPasswordMutation = useMutation({
    mutationFn: (data: ResetPasswordFormData) =>
      authClient.resetPassword({
        token: token || undefined,
        code: data.code,
        newPassword: data.newPassword,
      }),
    onSuccess: (response) => {
      if (response.success) {
        setIsSuccess(true)
      }
    },
    onError: (error: any) => {
      if (error.code === 'INVALID_TOKEN') {
        setError('root', {
          message: t('auth.resetPassword.errors.tokenInvalid'),
        })
      } else if (error.code === 'INVALID_CODE') {
        setError('code', {
          message: t('auth.resetPassword.errors.codeInvalid'),
        })
      } else {
        setError('root', {
          message: t('auth.resetPassword.errors.generic'),
        })
      }
    },
  })

  const onSubmit = (data: ResetPasswordFormData) => {
    resetPasswordMutation.mutate(data)
  }

  if (isSuccess) {
    return (
      <AuthCard
        title={ready ? t('auth.resetPasswordPage.success.title') : '密码已更新'}
        subtitle={ready ? t('auth.resetPasswordPage.success.desc') : '现在可以使用新密码登录。'}
        footer={
          <div className="text-center space-y-2">
            <button
              onClick={goToLogin}
              className="text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 font-medium transition-colors duration-200"
            >
              {t('auth.resetPasswordPage.success.action')}
            </button>
            <p className="text-xs text-stone-600 dark:text-stone-400">
              {t('auth.resetPasswordPage.notice.ssoHint')}
            </p>
          </div>
        }
      >
        <div className="text-center py-8">
          <div className="mx-auto w-16 h-16 bg-teal-100 dark:bg-teal-900/30 rounded-full flex items-center justify-center mb-6">
            <svg className="w-8 h-8 text-teal-600 dark:text-teal-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <Button onClick={goToLogin} className="text-sm">
            {t('auth.resetPasswordPage.success.action')}
          </Button>
        </div>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title={title}
      subtitle={subtitle}
        footer={
          <div className="text-center space-y-2">
            <button
              onClick={goToLogin}
              className="text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 font-medium transition-colors duration-200"
            >
              {t('auth.resetPasswordPage.actions.backToLogin')}
            </button>
            <p className="text-xs text-stone-600 dark:text-stone-400">
              {t('auth.resetPasswordPage.notice.ssoHint')}
            </p>
          </div>
        }
    >
      {/* Token 模式提示 */}
      {hasToken && (
        <div className="mb-4 p-3 bg-teal-50 dark:bg-teal-900/20 border border-teal-200 dark:border-teal-800 rounded-lg">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-teal-600 dark:text-teal-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <p className="text-xs text-teal-700 dark:text-teal-300">
              {t('auth.resetPasswordPage.tokenDetected')}
            </p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3.5">
        {/* 验证码字段（当没有token时显示） */}
        {!hasToken && (
          <div className="space-y-1">
            <Label htmlFor="code" className="text-xs font-medium">
              {t('auth.resetPasswordPage.fields.code.label')}
            </Label>
            <Input
              {...register('code')}
              id="code"
              type="text"
              placeholder={t('auth.resetPasswordPage.fields.code.placeholder')}
              className={errors.code ? 'border-red-500 focus-visible:ring-red-500' : ''}
            />
            {errors.code && (
              <p className="text-[11px] text-red-600 dark:text-red-400 mt-1 leading-4">
                {t(errors.code.message || 'common.error')}
              </p>
            )}
          </div>
        )}

        {/* 新密码字段 */}
        <div className="space-y-1">
          <Label htmlFor="newPassword" className="text-xs font-medium">
            {t('auth.resetPasswordPage.fields.newPassword.label')}
          </Label>
          <Input
            {...register('newPassword')}
            id="newPassword"
            type="password"
            placeholder={t('auth.resetPasswordPage.fields.newPassword.placeholder')}
            className={errors.newPassword ? 'border-red-500 focus-visible:ring-red-500' : ''}
            onFocus={() => {
              setPwdFocused(true)
              setPwdInteracted(true)
            }}
            onBlur={() => setPwdFocused(false)}
          />
          {errors.newPassword && (
            <p className="text-[11px] text-red-600 dark:text-red-400 mt-1 leading-4">
              {t(errors.newPassword.message || 'common.error')}
            </p>
          )}
          <PasswordStrengthHint
            visible={pwdFocused || pwdInteracted || watch('newPassword')?.length > 0}
            password={watch('newPassword') || ''}
            userInputs={[]} // 重置密码页面通常没有email上下文
            minLength={8}
          />
        </div>

        {/* 确认新密码字段 */}
        <div className="space-y-1">
          <Label htmlFor="confirmPassword" className="text-xs font-medium">
            {t('auth.resetPasswordPage.fields.confirmPassword.label')}
          </Label>
          <Input
            {...register('confirmPassword')}
            id="confirmPassword"
            type="password"
            placeholder={t('auth.resetPasswordPage.fields.confirmPassword.placeholder')}
            className={errors.confirmPassword ? 'border-red-500 focus-visible:ring-red-500' : ''}
          />
          {errors.confirmPassword && (
            <p className="text-[11px] text-red-600 dark:text-red-400 mt-1 leading-4">
              {t(errors.confirmPassword.message || 'common.error')}
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
          disabled={resetPasswordMutation.isPending}
          className="w-full mt-3 text-sm"
        >
          {resetPasswordMutation.isPending ? t('auth.resetPasswordPage.loading') : t('auth.resetPasswordPage.actions.submit')}
        </Button>
      </form>
    </AuthCard>
  )
}

export default ResetPasswordPage
