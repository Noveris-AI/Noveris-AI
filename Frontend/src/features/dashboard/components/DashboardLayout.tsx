import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { DashboardSidebar } from './DashboardSidebar'
import { DashboardHeader } from './DashboardHeader'

interface DashboardLayoutProps {
  onLogout?: () => void
}

export const DashboardLayout = ({ onLogout }: DashboardLayoutProps) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-stone-50 dark:bg-stone-900">
      {/* Sidebar */}
      <DashboardSidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Header */}
      <DashboardHeader
        onLogout={onLogout}
        sidebarCollapsed={sidebarCollapsed}
        notifications={[]}
      />

      {/* Main content */}
      <main
        className={`flex-1 pt-16 transition-all duration-300 overflow-hidden ${
          sidebarCollapsed ? 'pl-16' : 'pl-56'
        }`}
      >
        <div className="h-full p-6 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
