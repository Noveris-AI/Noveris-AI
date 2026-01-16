import { useTranslation } from 'react-i18next'

interface BrandMarkProps {
  className?: string
  showText?: boolean
}

export const BrandMark = ({ className = '', showText = true }: BrandMarkProps) => {
  const { t } = useTranslation()

  return (
    <div className={`flex items-center space-x-3 ${className}`}>
      {/* Logo */}
      <div className="flex-shrink-0">
        <img
          src="/logo.svg"
          alt={t('auth.brand.name')}
          className="h-8 w-8"
          onError={(e) => {
            // Fallback for missing logo
            const target = e.target as HTMLImageElement
            target.style.display = 'none'
            const fallback = target.parentElement?.querySelector('.fallback-logo')
            if (fallback) {
              (fallback as HTMLElement).style.display = 'flex'
            }
          }}
        />
        {/* Fallback logo */}
        <div className="fallback-logo hidden h-8 w-8 bg-teal-500 rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-sm">N</span>
        </div>
      </div>

      {/* Brand name */}
      {showText && (
        <span className="text-xl font-semibold text-stone-900 dark:text-stone-100">
          {t('auth.brand.name')}
        </span>
      )}
    </div>
  )
}
