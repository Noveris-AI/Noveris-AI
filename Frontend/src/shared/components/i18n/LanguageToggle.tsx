import { useTranslation } from 'react-i18next'
import { useState } from 'react'

const languages = [
  { code: 'zh-CN', name: '简体中文' },
  { code: 'en', name: 'English' },
]

export const LanguageToggle = () => {
  const { i18n, t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)

  const currentLang = languages.find(lang => lang.code === i18n.language) || languages[0]

  const handleLanguageChange = (langCode: string) => {
    i18n.changeLanguage(langCode)
    setIsOpen(false)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 p-2 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors duration-200 focus-ring"
        aria-label="选择语言 / Select Language"
        title="选择语言 / Select Language"
      >
        <span className="text-sm font-medium text-stone-700 dark:text-stone-300">
          {currentLang.name}
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
          <div className="absolute right-0 top-full mt-2 w-40 bg-white dark:bg-stone-900 rounded-lg shadow-lg border border-stone-200 dark:border-stone-700 z-[60]">
            {languages.map((lang) => (
              <button
                key={lang.code}
                onClick={() => handleLanguageChange(lang.code)}
                className={`w-full flex items-center justify-between px-4 py-3 text-left hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors duration-200 first:rounded-t-lg last:rounded-b-lg ${
                  i18n.language === lang.code ? 'bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300' : 'text-stone-700 dark:text-stone-300'
                }`}
              >
                <span className="text-sm font-medium">{lang.name}</span>
                {i18n.language === lang.code && (
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
