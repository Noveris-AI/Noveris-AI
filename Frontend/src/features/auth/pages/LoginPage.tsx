import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useTranslation } from 'react-i18next'
import { useMutation } from '@tanstack/react-query'
import { AuthCard } from '../components/AuthCard'
import { useAuthNavigation } from '../hooks/useAuthNavigation'
import { authClient } from '../api/authClient'
import { loginSchema, LoginFormData } from '../validation/schemas'
import { AUTH_CONFIG } from '@/shared/config/auth'
import { Input } from '@/shared/components/ui/Input'
import { Checkbox } from '@/shared/components/ui/Checkbox'
import { Label } from '@/shared/components/ui/Label'
import { Button } from '@/shared/components/ui/Button'

const LoginPage = () => {
  const { t } = useTranslation()
  const { goToRegister, goToForgotPassword, goToHome } = useAuthNavigation()

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
    setError,
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      rememberMe: false,
    },
  })

  const rememberMeValue = watch('rememberMe', false)

  const loginMutation = useMutation({
    mutationFn: authClient.login,
    onSuccess: (response) => {
      if (response.success) {
        goToHome()
      }
    },
    onError: (error: any) => {
      if (error.code === 'INVALID_CREDENTIALS') {
        setError('root', {
          message: t('auth.login.error.invalid'),
        })
      } else {
        setError('root', {
          message: t('auth.login.error.general'),
        })
      }
    },
  })

  const onSubmit = (data: LoginFormData) => {
    loginMutation.mutate(data)
  }

  const handleSSOLogin = () => {
    // TODO: 实现SSO登录逻辑
    console.log('SSO login clicked')
    // 这里可以调用真实的SSO登录API或重定向到SSO提供商
  }

  return (
    <AuthCard
      title={t('auth.login.title')}
      subtitle={t('auth.login.subtitle')}
      footer={
        <div className="text-center">
          <p className="text-xs text-stone-600 dark:text-stone-400">
            {t('auth.login.noAccount')}{' '}
            <button
              onClick={goToRegister}
              className="text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 font-medium transition-colors duration-200"
            >
              {t('auth.login.signUp')}
            </button>
          </p>
        </div>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3.5">
        {/* 邮箱字段 */}
        <div className="space-y-1">
          <Label htmlFor="email" className="text-xs font-medium">{t('auth.login.email.label')}</Label>
          <Input
            {...register('email')}
            id="email"
            type="email"
            placeholder={t('auth.login.email.placeholder')}
            className={errors.email ? 'border-red-500 focus-visible:ring-red-500' : ''}
          />
          {errors.email && (
            <p className="text-[11px] text-red-600 dark:text-red-400 mt-1 leading-4">
              {t(errors.email.message || 'common.error')}
            </p>
          )}
        </div>

        {/* 密码字段 */}
        <div className="space-y-1">
          <Label htmlFor="password" className="text-xs font-medium">{t('auth.login.password.label')}</Label>
          <Input
            {...register('password')}
            id="password"
            type="password"
            placeholder={t('auth.login.password.placeholder')}
            className={errors.password ? 'border-red-500 focus-visible:ring-red-500' : ''}
          />
        </div>

        {/* 记住我和忘记密码 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="rememberMe"
              checked={rememberMeValue}
              onCheckedChange={(checked) => setValue('rememberMe', checked as boolean)}
            />
            <Label
              htmlFor="rememberMe"
              className="text-xs font-normal text-stone-600 dark:text-stone-400"
            >
              {t('auth.login.rememberMe.label')}
            </Label>
          </div>

          <button
            type="button"
            onClick={goToForgotPassword}
            className="text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 font-medium transition-colors duration-200"
          >
            {t('auth.login.forgotPassword.link')}
          </button>
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
          disabled={loginMutation.isPending}
          className="w-full mt-3 text-sm"
        >
          {loginMutation.isPending ? t('auth.login.loading') : t('auth.login.submit')}
        </Button>

        {/* SSO登录按钮 - 可配置显示 */}
        {AUTH_CONFIG.SSO_ENABLED && (
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-stone-200 dark:border-stone-700" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-stone-50 dark:bg-stone-900 px-2 text-stone-500 dark:text-stone-400">
                {t('auth.login.or')}
              </span>
            </div>
          </div>
        )}

        {AUTH_CONFIG.SSO_ENABLED && (
          <Button
            type="button"
            variant="outline"
            onClick={handleSSOLogin}
            className="w-full text-sm"
          >
            {t('auth.login.ssoLogin')}
          </Button>
        )}
      </form>
    </AuthCard>
  )
}

export default LoginPage
