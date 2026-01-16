import { z } from 'zod'
import { validatePasswordStrength } from '@/shared/config/auth'

// 邮箱验证
const emailSchema = z
  .string()
  .min(1, 'auth.login.email.required')
  .email('auth.login.email.invalid')

// 密码验证
const passwordSchema = z
  .string()
  .min(1, 'auth.login.password.required')
  .refine(validatePasswordStrength, {
    message: 'auth.register.password.weak',
  })

// 确认密码验证
const confirmPasswordSchema = z
  .string()
  .min(1, 'auth.register.password.confirm.required')

// 登录表单验证
export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, 'auth.login.password.required'),
  rememberMe: z.boolean().optional(),
})

// 验证码验证
const verificationCodeSchema = z
  .string()
  .min(1, 'auth.register.verificationCode.required')
  .regex(/^\d{6}$/, 'auth.register.verificationCode.invalid')

// 注册表单验证
export const registerSchema = z
  .object({
    email: emailSchema,
    verificationCode: verificationCodeSchema,
    password: passwordSchema,
    confirmPassword: confirmPasswordSchema,
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'auth.register.password.confirm.mismatch',
    path: ['confirmPassword'],
  })

// 忘记密码表单验证
export const forgotPasswordSchema = z.object({
  email: emailSchema,
})

// 发送验证码表单验证
export const sendVerificationCodeSchema = z.object({
  email: emailSchema,
})

// 重置密码表单验证
export const resetPasswordSchema = z
  .object({
    code: z.string().optional(),
    newPassword: passwordSchema,
    confirmPassword: confirmPasswordSchema,
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: 'auth.resetPassword.confirmPassword.mismatch',
    path: ['confirmPassword'],
  })

// 类型导出
export type LoginFormData = z.infer<typeof loginSchema>
export type RegisterFormData = z.infer<typeof registerSchema>
export type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>
export type SendVerificationCodeFormData = z.infer<typeof sendVerificationCodeSchema>
export type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>
