/**
 * Settings Layout Component
 *
 * Provides the tabbed navigation for Settings pages.
 */

import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Shield,
  Palette,
  Bell,
  Lock,
  User,
  Sliders,
} from 'lucide-react';

const navItems = [
  {
    to: '/dashboard/settings',
    icon: Shield,
    label: 'settings.nav.auth',
    end: true,
  },
  {
    to: '/dashboard/settings/profile',
    icon: User,
    label: 'settings.nav.profile',
  },
  {
    to: '/dashboard/settings/branding',
    icon: Palette,
    label: 'settings.nav.branding',
  },
  {
    to: '/dashboard/settings/notifications',
    icon: Bell,
    label: 'settings.nav.notifications',
  },
  {
    to: '/dashboard/settings/security',
    icon: Lock,
    label: 'settings.nav.security',
  },
  {
    to: '/dashboard/settings/advanced',
    icon: Sliders,
    label: 'settings.nav.advanced',
  },
];

export function SettingsLayout() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900 px-6 py-4">
        <h1 className="text-xl font-semibold text-stone-900 dark:text-stone-100">
          {t('settings.title', 'Settings')}
        </h1>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
          {t('settings.description', 'Manage platform configuration, authentication, and security')}
        </p>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900">
        <nav className="flex space-x-1 px-6 overflow-x-auto" aria-label="Tabs">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
                  isActive
                    ? 'border-teal-500 text-teal-600 dark:text-teal-400'
                    : 'border-transparent text-stone-500 hover:text-stone-700 hover:border-stone-300 dark:text-stone-400 dark:hover:text-stone-300'
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              {t(item.label)}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6 bg-stone-50 dark:bg-stone-950">
        <Outlet />
      </div>
    </div>
  );
}

export default SettingsLayout;
