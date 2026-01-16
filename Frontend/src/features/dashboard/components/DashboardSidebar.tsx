import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { MenuItem } from '../types'
import { cn } from '@/shared/lib/utils'

const menuItems: MenuItem[] = [
  { id: 'home', label: '首页', labelKey: 'dashboard.menu.home', icon: 'Home', path: '/dashboard/homepage' },
  { id: 'monitoring', label: '监控面板', labelKey: 'dashboard.menu.monitoring', icon: 'Monitor', path: '/dashboard/monitoring' },
  { id: 'nodes', label: '节点管理', labelKey: 'dashboard.menu.nodes', icon: 'Server', path: '/dashboard/nodes' },
  { id: 'market', label: '模型市场', labelKey: 'dashboard.menu.market', icon: 'ShoppingBag', path: '/dashboard/market' },
  { id: 'deployment', label: '模型部署', labelKey: 'dashboard.menu.deployment', icon: 'Rocket', path: '/dashboard/deployment' },
  { id: 'forwarding', label: '模型转发', labelKey: 'dashboard.menu.forwarding', icon: 'GitBranch', path: '/dashboard/forwarding' },
  { id: 'chat', label: '聊天', labelKey: 'dashboard.menu.chat', icon: 'MessageSquare', path: '/dashboard/chat' },
  { id: 'permissions', label: '权限管理', labelKey: 'dashboard.menu.permissions', icon: 'Shield', path: '/dashboard/permissions' },
  { id: 'settings', label: '设置', labelKey: 'dashboard.menu.settings', icon: 'Settings', path: '/dashboard/settings' },
]

// Icon components mapping
const Icons: Record<string, React.ComponentType<{ className?: string }>> = {
  Home: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
    </svg>
  ),
  Monitor: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  ),
  Server: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
    </svg>
  ),
  ShoppingBag: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
    </svg>
  ),
  Rocket: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
    </svg>
  ),
  GitBranch: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
    </svg>
  ),
  MessageSquare: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  ),
  Shield: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  ),
  Settings: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
  ChevronLeft: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  ),
  ChevronRight: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  ),
  Minimize2: ({ className }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
    </svg>
  ),
}

interface DashboardSidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export const DashboardSidebar = ({ collapsed, onToggle }: DashboardSidebarProps) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()

  const handleItemClick = (item: MenuItem) => {
    navigate(item.path)
  }

  const isActive = (path: string) => {
    return location.pathname === path || location.pathname.startsWith(path + '/')
  }

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 h-full bg-white dark:bg-stone-900 border-r border-stone-200 dark:border-stone-700 transition-all duration-300 z-40 flex flex-col',
        collapsed ? 'w-16' : 'w-56'
      )}
    >
      {/* Logo area */}
      <div className="h-16 flex items-center justify-center border-b border-stone-200 dark:border-stone-700 px-3">
        {collapsed ? (
          <img src="/logo.svg" alt="N" className="h-8 w-8" />
        ) : (
          <div className="flex items-center space-x-2">
            <img src="/logo.svg" alt="Noveris" className="h-8 w-8" />
            <span className="text-lg font-semibold text-stone-900 dark:text-stone-100">Noveris</span>
          </div>
        )}
      </div>

      {/* Menu items */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        {menuItems.map((item) => {
          const Icon = Icons[item.icon]
          const active = isActive(item.path)

          return (
            <button
              key={item.id}
              onClick={() => handleItemClick(item)}
              className={cn(
                'w-full flex items-center px-3 py-2.5 rounded-lg transition-all duration-200 group relative',
                active
                  ? 'bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300'
                  : 'text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-800'
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className={cn(
                'flex-shrink-0 transition-colors',
                active ? 'text-teal-600 dark:text-teal-400' : 'text-stone-500 dark:text-stone-500 group-hover:text-stone-700 dark:group-hover:text-stone-300',
                collapsed ? 'w-5 h-5' : 'w-5 h-5 mr-3'
              )} />

              {!collapsed && (
                <span className="text-sm font-medium">{item.label}</span>
              )}

              {item.badge && !collapsed && (
                <span className="ml-auto bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                  {item.badge}
                </span>
              )}

              {collapsed && item.badge && (
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
              )}
            </button>
          )
        })}
      </nav>

      {/* Collapse button */}
      <div className="p-3 border-t border-stone-200 dark:border-stone-700">
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center px-3 py-2 rounded-lg text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors duration-200"
          title={collapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          {collapsed ? (
            <Icons.ChevronRight className="w-5 h-5" />
          ) : (
            <>
              <Icons.Minimize2 className="w-5 h-5 mr-2" />
              <span className="text-sm font-medium">收起</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
