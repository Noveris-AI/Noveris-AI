/**
 * Monitoring Layout Component
 *
 * Provides the layout for monitoring pages with navigation tabs
 */

import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard,
  Server,
  Cpu,
  Bot,
  Network,
  DollarSign,
  Shield,
  Activity,
} from 'lucide-react'
import { TimeRangePicker } from './TimeRangePicker'
import { ModeToggle } from './ModeToggle'
import { useState } from 'react'

const navItems = [
  { path: '/dashboard/monitoring', icon: LayoutDashboard, label: 'monitoring.nav.overview', end: true },
  { path: '/dashboard/monitoring/nodes', icon: Server, label: 'monitoring.nav.nodes' },
  { path: '/dashboard/monitoring/accelerators', icon: Cpu, label: 'monitoring.nav.accelerators' },
  { path: '/dashboard/monitoring/models', icon: Bot, label: 'monitoring.nav.models' },
  { path: '/dashboard/monitoring/gateway', icon: Network, label: 'monitoring.nav.gateway' },
  { path: '/dashboard/monitoring/cost', icon: DollarSign, label: 'monitoring.nav.cost' },
  { path: '/dashboard/monitoring/security', icon: Shield, label: 'monitoring.nav.security' },
]

export function MonitoringLayout() {
  const { t } = useTranslation()
  const location = useLocation()
  const [timeRange, setTimeRange] = useState('1h')
  const [displayMode, setDisplayMode] = useState<'simple' | 'advanced'>('simple')

  return (
    <div className="h-full flex flex-col">
      {/* Header with controls */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-stone-200 dark:border-stone-700">
        <div className="flex items-center space-x-6">
          <h1 className="text-xl font-semibold text-stone-900 dark:text-stone-100">
            {t('monitoring.title')}
          </h1>
          {/* Sub navigation */}
          <nav className="flex items-center space-x-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400'
                      : 'text-stone-600 hover:text-stone-900 hover:bg-stone-100 dark:text-stone-400 dark:hover:text-stone-100 dark:hover:bg-stone-800'
                  }`
                }
              >
                <item.icon className="w-4 h-4 mr-1.5" />
                {t(item.label)}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center space-x-4">
          <TimeRangePicker value={timeRange} onChange={setTimeRange} />
          <ModeToggle mode={displayMode} onChange={setDisplayMode} />
        </div>
      </div>

      {/* Page content */}
      <div className="flex-1 overflow-auto p-6">
        <Outlet context={{ timeRange, displayMode }} />
      </div>
    </div>
  )
}
