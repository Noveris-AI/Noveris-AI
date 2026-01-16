// Auth相关配置
export const AUTH_CONFIG = {
  // API模式：'mock' 或 'real'
  API_MODE: (import.meta.env.VITE_AUTH_API_MODE as 'mock' | 'real') || 'mock',

  // 登录成功后的跳转路径
  REDIRECT_AFTER_LOGIN: (import.meta.env.VITE_AUTH_REDIRECT_AFTER_LOGIN as string) || '/',

  // Mock模式下的模拟延迟 (毫秒)
  MOCK_DELAY_MIN: 300,
  MOCK_DELAY_MAX: 800,

  // 是否强制模拟失败 (用于测试错误状态)
  MOCK_FORCE_FAILURE: false,

  // 密码强度规则
  PASSWORD_RULES: {
    minLength: 8,
    requireUppercase: true,
    requireLowercase: true,
    requireNumbers: true,
    requireSpecialChars: true,
  },

  // SSO配置
  SSO_ENABLED: import.meta.env.VITE_SSO_ENABLED === 'true', // 是否启用SSO登录按钮

  // Session配置
  SESSION_KEY: 'session_id',
} as const

// 密码强度验证函数
export const validatePasswordStrength = (password: string): boolean => {
  const rules = AUTH_CONFIG.PASSWORD_RULES

  if (password.length < rules.minLength) return false
  if (rules.requireUppercase && !/[A-Z]/.test(password)) return false
  if (rules.requireLowercase && !/[a-z]/.test(password)) return false
  if (rules.requireNumbers && !/\d/.test(password)) return false
  if (rules.requireSpecialChars && !/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) return false

  return true
}

// 获取密码强度描述
export const getPasswordStrengthDescription = (): string => {
  const rules = AUTH_CONFIG.PASSWORD_RULES
  const requirements = []

  requirements.push(`${rules.minLength}个字符`)
  if (rules.requireUppercase) requirements.push('大写字母')
  if (rules.requireLowercase) requirements.push('小写字母')
  if (rules.requireNumbers) requirements.push('数字')
  if (rules.requireSpecialChars) requirements.push('特殊字符')

  return `至少包含${requirements.join('、')}`
}

// 计算密码强度分数 (0-4)
export const calculatePasswordStrength = (password: string): number => {
  if (!password) return 0

  let score = 0

  // 长度评分 (0-2分)
  if (password.length >= 8) score += 1
  if (password.length >= 12) score += 1

  // 字符类型多样性 (0-2分)
  const hasLower = /[a-z]/.test(password)
  const hasUpper = /[A-Z]/.test(password)
  const hasDigit = /\d/.test(password)
  const hasSpecial = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)

  const varietyCount = [hasLower, hasUpper, hasDigit, hasSpecial].filter(Boolean).length
  if (varietyCount >= 2) score += 1
  if (varietyCount >= 4) score += 1

  // 额外奖励：更长的密码或更多字符类型
  if (password.length >= 16) score = Math.min(score + 0.5, 4)

  return Math.min(Math.floor(score), 4)
}

// 获取密码强度详细信息
export const getPasswordStrengthDetails = (password: string) => {
  const length = password.length
  const hasLower = /[a-z]/.test(password)
  const hasUpper = /[A-Z]/.test(password)
  const hasDigit = /\d/.test(password)
  const hasSpecial = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)

  const missing = []
  if (length < 8) missing.push('至少8个字符')
  if (!hasLower) missing.push('小写字母')
  if (!hasUpper) missing.push('大写字母')
  if (!hasDigit) missing.push('数字')
  if (!hasSpecial) missing.push('特殊字符')

  return {
    length,
    hasLower,
    hasUpper,
    hasDigit,
    hasSpecial,
    missing,
    isValid: missing.length === 0
  }
}

// 获取密码强度文本描述
export const getPasswordStrengthText = (password: string): string => {
  const details = getPasswordStrengthDetails(password)

  if (details.missing.length > 0) {
    return `缺少：${details.missing.join('、')}`
  }

  const strength = calculatePasswordStrength(password)
  if (strength <= 1) return '密码强度较弱'
  if (strength === 2) return '密码强度一般'
  if (strength === 3) return '密码强度良好'
  return '密码强度很强'
}
