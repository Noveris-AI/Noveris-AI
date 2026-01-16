// src/features/auth/components/PasswordStrengthHint.tsx
import { useMemo } from "react";
import { usePasswordStrength } from "@/shared/hooks/usePasswordStrength";

type RuleItem = {
  key: string;
  ok: boolean;
  label: string;
};

export function PasswordStrengthHint(props: {
  visible: boolean; // 由页面控制：focus/touched/value => true
  password: string;
  userInputs?: string[]; // 可传 email 等，zxcvbn 会用来降低"包含个人信息"的密码评分
  minLength?: number; // 与你后端校验保持一致
}) {
  const { visible, password, userInputs = [], minLength = 8 } = props;

  // 确保所有 hooks 都在组件顶部调用，顺序固定
  const strength = usePasswordStrength({
    password,
    userInputs,
    enabled: true,
    debounceMs: 160,
  });

  const rules: RuleItem[] = useMemo(() => {
    const pw = password ?? "";
    const hasLower = /[a-z]/.test(pw);
    const hasUpper = /[A-Z]/.test(pw);
    const hasDigit = /\d/.test(pw);
    const hasSymbol = /[^A-Za-z0-9]/.test(pw);

    return [
      {
        key: "minLength",
        ok: pw.length >= minLength,
        label: `至少 ${minLength} 位`,
      },
      {
        key: "upper",
        ok: hasUpper,
        label: "大写字母",
      },
      {
        key: "lower",
        ok: hasLower,
        label: "小写字母",
      },
      {
        key: "digit",
        ok: hasDigit,
        label: "数字",
      },
      {
        key: "symbol",
        ok: hasSymbol,
        label: "特殊字符",
      },
    ];
  }, [password, minLength]);

  const compactHintText = useMemo(() => {
    if (password.length === 0) {
      return "请输入密码以评估强度";
    }

    const unmetRules = rules.filter(r => !r.ok).map(r => r.label);
    if (unmetRules.length > 0) {
      return `缺少：${unmetRules.join('、')}`;
    }

    return strength.level === 'strong' ? '密码强度很强' :
           strength.level === 'good' ? '密码强度良好' :
           strength.level === 'fair' ? '密码强度一般' :
           '密码强度较弱';
  }, [password.length, rules, strength.level]);

  // 条件渲染只在最后进行
  if (!visible) return <div style={{ display: 'none' }} />;

  return (
    <div className="mt-2">
      <p className="text-xs text-muted-foreground" aria-live="polite" role="status">
        {compactHintText}
      </p>
    </div>
  );
}
