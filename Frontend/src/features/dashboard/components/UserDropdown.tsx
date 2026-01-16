import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { cn } from '@/shared/lib/utils'
import { useAuthz } from '@/features/authz/hooks/AuthzContext'

interface UserDropdownProps {
  onLogout?: () => void
}

// Role badge color mapping
const getRoleColor = (roleName: string): string => {
  const roleColorMap: Record<string, string> = {
    admin: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
    administrator: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
    operator: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    viewer: 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
    member: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  }
  const lowerName = roleName.toLowerCase()
  return roleColorMap[lowerName] || roleColorMap['viewer']
}

const getInitials = (displayName: string) => {
  if (!displayName) return '?'
  return displayName
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

export const UserDropdown = ({ onLogout }: UserDropdownProps) => {
  // All hooks must be called unconditionally at the top
  const [isOpen, setIsOpen] = useState(false)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { name, email, roles, isSuperAdmin, isLoading } = useAuthz()

  const handleLogout = useCallback(() => {
    setIsOpen(false)
    onLogout?.()
    navigate('/auth/login')
  }, [onLogout, navigate])

  const handleNavigate = useCallback((path: string) => {
    setIsOpen(false)
    navigate(path)
  }, [navigate])

  // Early returns must come AFTER all hooks
  // Loading skeleton
  if (isLoading) {
    return (
      <div className="flex items-center space-x-3 p-2 pr-3">
        <div className="w-8 h-8 bg-stone-200 dark:bg-stone-700 rounded-full animate-pulse" />
        <div className="hidden md:block space-y-1">
          <div className="h-4 w-20 bg-stone-200 dark:bg-stone-700 rounded animate-pulse" />
          <div className="h-3 w-16 bg-stone-200 dark:bg-stone-700 rounded animate-pulse" />
        </div>
      </div>
    )
  }

  // Computed values (after hooks and early returns)
  const displayName = name || email || 'User'
  const primaryRole = isSuperAdmin
    ? t('user.superAdmin')
    : roles[0]?.title || roles[0]?.name || t('user.member')
  const roleColor = getRoleColor(primaryRole)

  return (
    <div className="relative">
      {/* User info button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        className="flex items-center space-x-3 p-2 pr-3 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 dark:focus:ring-offset-stone-900"
      >
        {/* Avatar */}
        <div className="w-8 h-8 bg-teal-500 rounded-full flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
          <span>{getInitials(displayName)}</span>
        </div>

        {/* User info - hidden on mobile */}
        <div className="hidden md:block text-left">
          <p className="text-sm font-medium text-stone-900 dark:text-stone-100 leading-tight truncate max-w-[120px]">
            {displayName}
          </p>
          <p className="text-xs text-stone-500 dark:text-stone-400 leading-tight">
            {primaryRole}
          </p>
        </div>

        {/* Dropdown arrow */}
        <svg
          className={cn(
            'w-4 h-4 text-stone-500 transition-transform duration-200',
            isOpen && 'rotate-180'
          )}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
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
          <div
            className="absolute right-0 top-full mt-2 w-60 bg-white dark:bg-stone-900 rounded-xl shadow-lg border border-stone-200 dark:border-stone-700 z-[60] overflow-hidden"
            role="menu"
          >
            {/* User info header */}
            <div className="px-4 py-3 border-b border-stone-200 dark:border-stone-700">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-teal-500 rounded-full flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                  <span>{getInitials(displayName)}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-stone-900 dark:text-stone-100 truncate">
                    {displayName}
                  </p>
                  <p className="text-xs text-stone-500 dark:text-stone-400 truncate">
                    {email}
                  </p>
                </div>
              </div>
              <span className={cn('inline-flex mt-2 px-2 py-0.5 text-xs font-medium rounded-full', roleColor)}>
                {primaryRole}
              </span>
            </div>

            {/* Menu items */}
            <div className="py-1" role="none">
              {/* Profile */}
              <button
                onClick={() => handleNavigate('/dashboard/settings/profile')}
                className="w-full flex items-center px-4 py-2.5 text-sm text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors duration-150"
                role="menuitem"
              >
                <svg className="w-4 h-4 mr-3 text-stone-500 dark:text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                {t('user.profile')}
              </button>

              {/* Security & Sessions */}
              <button
                onClick={() => handleNavigate('/dashboard/settings/security')}
                className="w-full flex items-center px-4 py-2.5 text-sm text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors duration-150"
                role="menuitem"
              >
                <svg className="w-4 h-4 mr-3 text-stone-500 dark:text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                {t('user.security')}
              </button>

              {/* Notifications */}
              <button
                onClick={() => handleNavigate('/dashboard/settings/notifications')}
                className="w-full flex items-center px-4 py-2.5 text-sm text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors duration-150"
                role="menuitem"
              >
                <svg className="w-4 h-4 mr-3 text-stone-500 dark:text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                {t('user.notifications')}
              </button>
            </div>

            {/* Help & About section */}
            <div className="py-1 border-t border-stone-200 dark:border-stone-700" role="none">
              {/* Help & Documentation */}
              <button
                onClick={() => window.open('https://docs.noveris.ai', '_blank')}
                className="w-full flex items-center px-4 py-2.5 text-sm text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors duration-150"
                role="menuitem"
              >
                <svg className="w-4 h-4 mr-3 text-stone-500 dark:text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {t('user.help')}
                <svg className="w-3 h-3 ml-auto text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </button>

              {/* About */}
              <button
                onClick={() => handleNavigate('/dashboard/settings/advanced')}
                className="w-full flex items-center px-4 py-2.5 text-sm text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors duration-150"
                role="menuitem"
              >
                <svg className="w-4 h-4 mr-3 text-stone-500 dark:text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {t('user.about')}
              </button>
            </div>

            {/* Logout */}
            <div className="py-1 border-t border-stone-200 dark:border-stone-700" role="none">
              <button
                onClick={handleLogout}
                className="w-full flex items-center px-4 py-2.5 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors duration-150"
                role="menuitem"
              >
                <svg className="w-4 h-4 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                {t('user.logout')}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
