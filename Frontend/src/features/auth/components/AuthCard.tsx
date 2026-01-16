import { ReactNode } from 'react'

interface AuthCardProps {
  title: string
  subtitle?: string
  children: ReactNode
  footer?: ReactNode
}

export const AuthCard = ({ title, subtitle, children, footer }: AuthCardProps) => {
  return (
    <div className="w-full space-y-4">
      {/* 标题区域 */}
      <div>
        <h1 className="text-lg font-semibold text-stone-900 dark:text-stone-100 tracking-tight">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1 text-stone-600 dark:text-stone-400 text-xs">
            {subtitle}
          </p>
        )}
      </div>

      {/* 表单内容 */}
      <div className="space-y-3.5">
        {children}
      </div>

      {/* 底部链接 */}
      {footer && (
        <div className="mt-4">
          <div className="h-[1.5px] bg-stone-200/80 dark:bg-stone-700/80" />
          <div className="pt-3">
            {footer}
          </div>
        </div>
      )}
    </div>
  )
}