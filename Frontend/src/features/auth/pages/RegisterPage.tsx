import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useTranslation } from 'react-i18next'
import { useMutation } from '@tanstack/react-query'
import { AuthCard } from '../components/AuthCard'
import { PasswordStrengthHint } from '../components/PasswordStrengthHint'
import { useAuthNavigation } from '../hooks/useAuthNavigation'
import { authClient } from '../api/authClient'
import { registerSchema, RegisterFormData } from '../validation/schemas'
import { Input } from '@/shared/components/ui/Input'
import { Label } from '@/shared/components/ui/Label'
import { Button } from '@/shared/components/ui/Button'
const RegisterPage = () => {
  const { t, ready } = useTranslation()
  const { goToLogin } = useAuthNavigation()
  const [countdown, setCountdown] = useState(0)
  const [pwdFocused, setPwdFocused] = useState(false)
  const [pwdInteracted, setPwdInteracted] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
    setError,
    watch,
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    mode: 'onBlur',  // Validate on blur to allow watching values
  })

  // Watch email value for send code functionality
  const emailValue = watch('email')
  const passwordValue = watch('password')


  // 倒计时效果
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [countdown])

  const sendCodeMutation = useMutation({
    mutationFn: authClient.sendVerificationCode,
    onSuccess: () => {
      setCountdown(60) // 60秒倒计时
    },
            onError: () => {
                setError('root', {
                  message: ready ? t('auth.register.verificationCode.sendFailed', { defaultValue: 'Failed to send verification code' }) : '发送验证码失败',
                })
            },
          })

          const registerMutation = useMutation({
            mutationFn: authClient.register,
            onSuccess: (response) => {
              if (response.success) {
                goToLogin()
              }
            },
            onError: (error: any) => {
              if (error.code === 'EMAIL_EXISTS') {
                setError('email', {
                  message: t('auth.register.email.exists'),
                })
              } else if (error.code === 'VERIFICATION_CODE_EXPIRED') {
                setError('verificationCode', {
                  message: t('auth.register.verificationCode.expired'),
                })
              } else if (error.code === 'INVALID_VERIFICATION_CODE') {
                setError('verificationCode', {
                  message: t('auth.register.verificationCode.invalidCode'),
                })
              } else {
                setError('root', {
                  message: t('auth.register.error.general'),
                })
              }
            },
          })

  const handleSendCode = () => {
    if (!emailValue || emailValue.trim() === '') {
      setError('email', {
        message: t('auth.register.email.required'),
      })
      return
    }
    sendCodeMutation.mutate({ email: emailValue })
  }

  const onSubmit = (data: RegisterFormData) => {
    registerMutation.mutate(data)
  }

  return (
    <AuthCard
      title={t('auth.register.title')}
      subtitle={t('auth.register.subtitle')}
      footer={
        <div className="text-center">
          <p className="text-xs text-stone-600 dark:text-stone-400">
            {t('auth.register.hasAccount')}{' '}
            <button
              onClick={goToLogin}
              className="text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 font-medium transition-colors duration-200"
            >
              {t('auth.register.signIn')}
            </button>
          </p>
        </div>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        {/* 邮箱字段 */}
        <div className="space-y-1">
          <Label htmlFor="email" className="text-xs font-medium">
            {t('auth.register.email.label')}
          </Label>
          <Input
            {...register('email')}
            id="email"
            type="email"
            placeholder={t('auth.register.email.placeholder')}
            className={errors.email ? 'border-red-500 focus-visible:ring-red-500' : ''}
          />
          {errors.email && (
            <p className="text-[11px] text-red-600 dark:text-red-400 mt-1 leading-4">
              {t(errors.email.message || 'common.error')}
            </p>
          )}
        </div>

        {/* 验证码字段 */}
        <div className="space-y-1">
          <Label htmlFor="verificationCode" className="text-xs font-medium">
            {t('auth.register.verificationCode.label')}
          </Label>
          <div className="flex items-center gap-2.5">
            <Input
              {...register('verificationCode')}
              id="verificationCode"
              type="text"
              placeholder={t('auth.register.verificationCode.placeholder')}
              className={`flex-1 text-center font-mono tracking-wider ${errors.verificationCode ? 'border-red-500 focus-visible:ring-red-500' : ''}`}
              maxLength={6}
            />
            <Button
              type="button"
              variant="outline"
              onClick={handleSendCode}
              disabled={countdown > 0 || sendCodeMutation.isPending}
              className="min-w-[96px] text-xs whitespace-nowrap"
            >
              {sendCodeMutation.isPending
                ? t('auth.register.verificationCode.sending')
                : countdown > 0
                ? `${countdown}s`
                : t('auth.register.verificationCode.send')
              }
            </Button>
          </div>
          {errors.verificationCode && (
            <p className="text-[11px] text-red-600 dark:text-red-400 mt-1 leading-4">
              {t(errors.verificationCode.message || 'common.error')}
            </p>
          )}
          {sendCodeMutation.isSuccess && countdown === 0 && !errors.verificationCode && (
            <p className="text-[11px] text-green-600 dark:text-green-400 mt-1 leading-4">
              {t('auth.register.verificationCode.sent')}
            </p>
          )}
        </div>

        {/* 密码字段 */}
        <div className="space-y-1">
          <Label htmlFor="password" className="text-xs font-medium">
            {t('auth.register.password.label')}
          </Label>
          <Input
            {...register('password')}
            id="password"
            type="password"
            placeholder={t('auth.register.password.placeholder')}
            className={errors.password ? 'border-red-500 focus-visible:ring-red-500' : ''}
            onFocus={() => {
              setPwdFocused(true)
              setPwdInteracted(true)
            }}
            onBlur={() => setPwdFocused(false)}
          />
          {errors.password && (
            <p className="text-[11px] text-red-600 dark:text-red-400 mt-1 leading-4">
              {t(errors.password.message || 'common.error')}
            </p>
          )}
          <PasswordStrengthHint
            visible={pwdFocused || pwdInteracted || (passwordValue && passwordValue.length > 0)}
            password={passwordValue || ''}
            userInputs={[emailValue].filter(Boolean)}
            minLength={8}
          />
        </div>

        {/* 确认密码字段 */}
        <div className="space-y-1">
          <Label htmlFor="confirmPassword" className="text-xs font-medium">
            {t('auth.register.password.confirm.label')}
          </Label>
          <Input
            {...register('confirmPassword')}
            id="confirmPassword"
            type="password"
            placeholder={t('auth.register.password.confirm.placeholder')}
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
          <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
            <p className="text-[11px] text-red-600 dark:text-red-400 leading-4">
              {errors.root.message}
            </p>
          </div>
        )}

        {/* 提交按钮 */}
        <Button
          type="submit"
          disabled={registerMutation.isPending}
          className="w-full mt-3 text-sm"
        >
          {registerMutation.isPending ? t('auth.register.loading') : t('auth.register.submit')}
        </Button>
      </form>
    </AuthCard>
  )
}

export default RegisterPage
