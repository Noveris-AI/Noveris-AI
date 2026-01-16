import { useState, forwardRef, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { FieldError } from 'react-hook-form'
import { calculatePasswordStrength, getPasswordStrengthText } from '@/shared/config/auth'

interface PasswordFieldProps {
  label: string
  placeholder?: string
  error?: FieldError
  showStrengthIndicator?: boolean
  className?: string
  [key: string]: any
}

export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
  ({ label, placeholder, error, showStrengthIndicator = false, className = '', ...props }, ref) => {
    const { t } = useTranslation()
    const [showPassword, setShowPassword] = useState(false)
    const [passwordValue, setPasswordValue] = useState('')
    const [currentStrength, setCurrentStrength] = useState(0)

    const togglePasswordVisibility = () => {
      setShowPassword(!showPassword)
    }

    // 防抖计算密码强度
    const updatePasswordStrength = useCallback((value: string) => {
      const strength = calculatePasswordStrength(value)
      setCurrentStrength(strength)
    }, [])

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = e.target.value
      setPasswordValue(newValue)

      // 立即更新强度（对于空字符串和短密码）
      if (newValue.length <= 2) {
        updatePasswordStrength(newValue)
      } else {
        // 对于较长的密码，使用 requestAnimationFrame 优化性能
        requestAnimationFrame(() => updatePasswordStrength(newValue))
      }

      if (props.onChange) {
        props.onChange(e)
      }
    }

    // 初始化强度检测状态
    useEffect(() => {
      if (props.defaultValue) {
        const defaultValue = props.defaultValue as string
        setPasswordValue(defaultValue)
        updatePasswordStrength(defaultValue)
      }
    }, [props.defaultValue, updatePasswordStrength])

    return (
      <div className={className}>
        {/* 输入框容器 */}
        <div className="relative">
          <input
            ref={ref}
            type={showPassword ? 'text' : 'password'}
            placeholder={placeholder ? t(placeholder) : undefined}
            className={`input-field pr-9 h-9 ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''}`}
            onChange={handleInputChange}
            {...props}
          />

          {/* 切换可见性按钮 */}
          <button
            type="button"
            onClick={togglePasswordVisibility}
            className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 flex items-center justify-center text-stone-500 hover:text-stone-700 dark:text-stone-400 dark:hover:text-stone-200 transition-colors duration-200 focus:outline-none focus:text-stone-700 dark:focus:text-stone-200 rounded-md"
            aria-label={t('auth.login.password.toggleVisibility')}
          >
            {showPassword ? (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            )}
          </button>
        </div>

        {/* 错误信息 */}
        {error && (
          <p className="mt-1 text-sm text-red-600 dark:text-red-400">
            {t(error.message || 'common.error')}
          </p>
        )}

        {/* 密码强度指示器 */}
        {showStrengthIndicator && (
          <div className="mt-1.5">
            <div className="flex space-x-0.5 mb-1">
              {[0, 1, 2, 3].map((index) => {
                // 根据密码强度决定每条的颜色
                const getBarColor = () => {
                  if (index > currentStrength - 1) return 'bg-stone-200 dark:bg-stone-700'

                  if (currentStrength <= 1) return 'bg-red-500'
                  if (currentStrength === 2) return 'bg-orange-500'
                  if (currentStrength === 3) return 'bg-yellow-500'
                  return 'bg-green-500'
                }

                return (
                  <div
                    key={index}
                    className={`h-0.5 flex-1 rounded-full transition-colors duration-300 ${getBarColor()}`}
                  />
                )
              })}
            </div>
            <p className={`text-[11px] leading-4 transition-colors duration-300 ${
              passwordValue.length === 0
                ? 'text-stone-500 dark:text-stone-400'
                : currentStrength <= 1
                ? 'text-red-600 dark:text-red-400'
                : currentStrength === 2
                ? 'text-orange-600 dark:text-orange-400'
                : currentStrength === 3
                ? 'text-yellow-600 dark:text-yellow-400'
                : 'text-green-600 dark:text-green-400'
            }`}>
              {passwordValue.length === 0
                ? '密码至少需要8个字符，包含大小写字母、数字和特殊字符'
                : getPasswordStrengthText(passwordValue)}
            </p>
          </div>
        )}
      </div>
    )
  }
)

PasswordField.displayName = 'PasswordField'
