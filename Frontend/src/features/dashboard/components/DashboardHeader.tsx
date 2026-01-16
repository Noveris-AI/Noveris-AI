import { LanguageToggle } from '@/shared/components/i18n/LanguageToggle'
import { ThemeToggle } from '@/shared/components/theme/ThemeToggle'
import { NotificationDropdown } from './NotificationDropdown'
import { UserDropdown } from './UserDropdown'
import { Notification } from '../types'

interface DashboardHeaderProps {
  onLogout?: () => void
  sidebarCollapsed: boolean
  notifications?: Notification[]
}

export const DashboardHeader = ({ onLogout, sidebarCollapsed, notifications = [] }: DashboardHeaderProps) => {
  return (
    <header className="h-16 bg-white dark:bg-stone-900 border-b border-stone-200 dark:border-stone-700 fixed top-0 right-0 left-0 z-30 flex items-center justify-between px-4">
      {/* Left spacer for sidebar */}
      <div className="w-56 lg:w-56 flex-shrink-0" />
      <div className={`hidden ${sidebarCollapsed ? 'w-16' : 'w-56'} lg:block flex-shrink-0`} />

      {/* Right side actions */}
      <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center space-x-2">
        {/* Language Toggle */}
        <LanguageToggle />

        {/* Theme Toggle */}
        <ThemeToggle />

        {/* Divider */}
        <div className="h-6 w-px bg-stone-200 dark:bg-stone-700 mx-1" />

        {/* Notifications */}
        <NotificationDropdown notifications={notifications} />

        {/* User Menu */}
        <UserDropdown onLogout={onLogout} />
      </div>
    </header>
  )
}
