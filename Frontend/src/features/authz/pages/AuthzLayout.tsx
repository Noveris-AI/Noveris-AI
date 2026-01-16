/**
 * Authorization Management Layout
 */

import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Shield, Users, Key, Layers, History } from 'lucide-react';
import { RequirePermission } from '../components/PermissionGate';

const navItems = [
  {
    to: '/dashboard/permissions',
    icon: Shield,
    label: 'authz.nav.overview',
    permission: 'security.permission.view',
    end: true,
  },
  {
    to: '/dashboard/permissions/modules',
    icon: Layers,
    label: 'authz.nav.modules',
    permission: 'security.module.view',
  },
  {
    to: '/dashboard/permissions/roles',
    icon: Key,
    label: 'authz.nav.roles',
    permission: 'security.role.view',
  },
  {
    to: '/dashboard/permissions/users',
    icon: Users,
    label: 'authz.nav.users',
    permission: 'security.user.view',
  },
  {
    to: '/dashboard/permissions/audit',
    icon: History,
    label: 'authz.nav.audit',
    permission: 'security.audit.view',
  },
];

export function AuthzLayout() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900 px-6 py-4">
        <h1 className="text-xl font-semibold text-stone-900 dark:text-stone-100">
          {t('authz.title', 'Permission Management')}
        </h1>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
          {t('authz.description', 'Manage roles, permissions, and access control')}
        </p>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900">
        <nav className="flex space-x-1 px-6" aria-label="Tabs">
          {navItems.map((item) => (
            <RequirePermission key={item.to} permission={item.permission}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
                    isActive
                      ? 'border-teal-500 text-teal-600 dark:text-teal-400'
                      : 'border-transparent text-stone-500 hover:text-stone-700 hover:border-stone-300 dark:text-stone-400 dark:hover:text-stone-300'
                  }`
                }
              >
                <item.icon className="h-4 w-4" />
                {t(item.label)}
              </NavLink>
            </RequirePermission>
          ))}
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <Outlet />
      </div>
    </div>
  );
}

export default AuthzLayout;
