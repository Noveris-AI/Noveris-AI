import { useTheme } from './ThemeProvider'
import { useTranslation } from 'react-i18next'
import { useState } from 'react'

const themes = [
  { code: 'light', name: '明亮' },
  { code: 'dark', name: '暗黑' },
]

export const ThemeToggle = () => {
  const { theme, setTheme } = useTheme()
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)

  const currentTheme = themes.find(t => t.code === theme) || themes[0]

  const handleThemeChange = (themeCode: string) => {
    setTheme(themeCode as 'light' | 'dark')
    setIsOpen(false)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 p-2 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors duration-200 focus-ring"
        aria-label="选择主题 / Select Theme"
        title="选择主题 / Select Theme"
      >
        <span className="text-sm font-medium text-stone-700 dark:text-stone-300">
          {currentTheme.name}
        </span>
        <svg className="w-4 h-4 text-stone-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-[55]"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-2 w-32 bg-white dark:bg-stone-900 rounded-lg shadow-lg border border-stone-200 dark:border-stone-700 z-[60]">
            {themes.map((themeOption) => (
              <button
                key={themeOption.code}
                onClick={() => handleThemeChange(themeOption.code)}
                className={`w-full flex items-center justify-between px-4 py-3 text-left hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors duration-200 first:rounded-t-lg last:rounded-b-lg ${
                  theme === themeOption.code ? 'bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300' : 'text-stone-700 dark:text-stone-300'
                }`}
              >
                <span className="text-sm font-medium">{themeOption.name}</span>
                {theme === themeOption.code && (
                  <svg className="w-4 h-4 text-teal-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
