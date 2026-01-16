/**
 * Gateway Layout with Sub-navigation
 *
 * Uses a tabbed navigation style consistent with the project design.
 */

import { NavLink, Outlet, useLocation } from 'react-router-dom'

const tabs = [
  { path: '', label: '概览', end: true },
  { path: 'upstreams', label: '上游服务', end: false },
  { path: 'models', label: '虚拟模型', end: false },
  { path: 'routes', label: '路由策略', end: false },
  { path: 'api-keys', label: 'API 密钥', end: false },
  { path: 'logs', label: '请求日志', end: false },
]

export default function GatewayLayout() {
  const location = useLocation()

  return (
    <div className="space-y-6">
      {/* Sub-navigation */}
      <div className="border-b border-stone-200 dark:border-stone-700">
        <nav className="flex space-x-1 -mb-px" aria-label="Tabs">
          {tabs.map((tab) => (
            <NavLink
              key={tab.path}
              to={tab.path}
              end={tab.end}
              className={({ isActive }) =>
                `px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  isActive
                    ? 'border-teal-500 text-teal-600 dark:text-teal-400'
                    : 'border-transparent text-stone-500 hover:text-stone-700 hover:border-stone-300 dark:text-stone-400 dark:hover:text-stone-300'
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Page Content */}
      <Outlet />
    </div>
  )
}
