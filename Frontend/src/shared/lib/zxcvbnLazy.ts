// src/shared/lib/zxcvbnLazy.ts
export type ZxcvbnScore = 0 | 1 | 2 | 3 | 4;

export type ZxcvbnResult = {
  score: ZxcvbnScore;
  feedback?: {
    warning?: string;
    suggestions?: string[];
  };
};

export type ZxcvbnFn = (password: string, userInputs?: string[]) => ZxcvbnResult;

// 简化的密码强度计算（作为zxcvbn的fallback）
function calculatePasswordStrength(password: string): ZxcvbnScore {
  if (!password) return 0

  let score = 0
  const rules = {
    minLength: 8,
    requireUppercase: true,
    requireLowercase: true,
    requireNumbers: true,
    requireSpecialChars: true
  }

  // 基础长度检查
  if (password.length >= rules.minLength) score += 1

  // 字符类型检查
  if (rules.requireUppercase && /[A-Z]/.test(password)) score += 1
  if (rules.requireLowercase && /[a-z]/.test(password)) score += 1
  if (rules.requireNumbers && /\d/.test(password)) score += 1
  if (rules.requireSpecialChars && /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) score += 1

  // 额外奖励：更长的密码
  if (password.length >= rules.minLength + 4) score = Math.min(score + 1, 4)

  return Math.min(score, 4) as ZxcvbnScore
}

/**
 * 模拟 zxcvbn 加载（实际使用内置算法）
 */
let cached: Promise<ZxcvbnFn> | null = null;

export function loadZxcvbn(): Promise<ZxcvbnFn> {
  if (!cached) {
    cached = Promise.resolve((password: string, userInputs?: string[]) => ({
      score: calculatePasswordStrength(password),
      feedback: undefined
    }));
  }
  return cached;
}
