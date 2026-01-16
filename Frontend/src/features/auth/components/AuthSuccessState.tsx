import { useTranslation } from 'react-i18next'
import { Button } from '@/shared/components/ui/Button'

interface AuthSuccessStateProps {
  title: string
  message: string
  actionText: string
  onAction: () => void
}

export const AuthSuccessState = ({
  title,
  message,
  actionText,
  onAction
}: AuthSuccessStateProps) => {
  const { t } = useTranslation()

  return (
    <div className="text-center py-6">
      {/* 成功图标 */}
      <div className="mx-auto w-14 h-14 bg-teal-100 dark:bg-teal-900/30 rounded-full flex items-center justify-center mb-4">
        <svg className="w-7 h-7 text-teal-600 dark:text-teal-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>

      {/* 标题和消息 */}
      <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-2">
        {t(title)}
      </h2>
      <p className="text-stone-600 dark:text-stone-400 mb-5 text-sm">
        {t(message)}
      </p>

      {/* 操作按钮 */}
      <Button
        onClick={onAction}
        className="text-sm"
      >
        {t(actionText)}
      </Button>
    </div>
  )
}
