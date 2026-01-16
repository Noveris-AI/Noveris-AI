// src/shared/hooks/usePasswordStrength.ts
import { useEffect, useMemo, useState } from "react";
import { loadZxcvbn, type ZxcvbnScore } from "@/shared/lib/zxcvbnLazy";

export type PasswordStrengthState = {
  isEmpty: boolean;
  score: ZxcvbnScore;
  /**
   * 用于 UI 文案映射（走 i18n 更好）
   * empty / very_weak / weak / fair / good / strong
   */
  level: "empty" | "very_weak" | "weak" | "fair" | "good" | "strong";
  /** 0~1，用于进度条展示 */
  percent: number;
};

function clampScore(n: number): ZxcvbnScore {
  if (n <= 0) return 0;
  if (n === 1) return 1;
  if (n === 2) return 2;
  if (n === 3) return 3;
  return 4;
}

function levelFromScore(score: ZxcvbnScore): PasswordStrengthState["level"] {
  switch (score) {
    case 0:
      return "very_weak";
    case 1:
      return "weak";
    case 2:
      return "fair";
    case 3:
      return "good";
    case 4:
      return "strong";
    default:
      return "very_weak";
  }
}

/**
 * 兜底的轻量评分（当 zxcvbn 未加载成功或被禁用时用）
 * 规则：长度 + 字符种类。不要做过度复杂化。
 */
function fallbackScore(password: string): ZxcvbnScore {
  const pw = password ?? "";
  if (pw.length === 0) return 0;

  const hasLower = /[a-z]/.test(pw);
  const hasUpper = /[A-Z]/.test(pw);
  const hasDigit = /\d/.test(pw);
  const hasSymbol = /[^A-Za-z0-9]/.test(pw);
  const types = [hasLower, hasUpper, hasDigit, hasSymbol].filter(Boolean).length;

  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (types >= 2) s++;
  if (types >= 3 && pw.length >= 12) s++;

  return clampScore(s);
}

export function usePasswordStrength(params: {
  password: string;
  userInputs?: string[];
  enabled?: boolean;
  debounceMs?: number;
}): PasswordStrengthState {
  const {
    password,
    userInputs = [],
    enabled = true,
    debounceMs = 160,
  } = params;

  const userInputsKey = useMemo(
    () => userInputs.filter(Boolean).join("\u0000"),
    [userInputs]
  );

  const [state, setState] = useState<PasswordStrengthState>(() => ({
    isEmpty: true,
    score: 0,
    level: "empty",
    percent: 0,
  }));

  useEffect(() => {
    // 无论 enabled 与否，空态都应返回可渲染的状态
    if (!password) {
      setState({
        isEmpty: true,
        score: 0,
        level: "empty",
        percent: 0,
      });
      return;
    }

    if (!enabled) {
      const score = fallbackScore(password);
      setState({
        isEmpty: false,
        score,
        level: levelFromScore(score),
        percent: (score + 1) / 5,
      });
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const zxcvbn = await loadZxcvbn();
        const result = zxcvbn(password, userInputs.filter(Boolean));
        if (cancelled) return;

        const score = clampScore(result?.score ?? 0);
        setState({
          isEmpty: false,
          score,
          level: levelFromScore(score),
          percent: (score + 1) / 5,
        });
      } catch {
        if (cancelled) return;
        const score = fallbackScore(password);
        setState({
          isEmpty: false,
          score,
          level: levelFromScore(score),
          percent: (score + 1) / 5,
        });
      }
    }, debounceMs);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [password, userInputsKey, enabled, debounceMs]);

  return state;
}
