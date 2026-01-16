/**
 * Permissions Overview Page
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Search, ChevronDown, ChevronRight, Shield, Check, X } from 'lucide-react';
import { authzClient } from '../api/authzClient';
import type { PermissionGroup, Permission } from '../api/authzTypes';

export function PermissionsPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());

  const { data: permissionGroups, isLoading } = useQuery({
    queryKey: ['permissions', 'grouped'],
    queryFn: () => authzClient.listPermissionsGrouped(),
  });

  const toggleModule = (moduleKey: string) => {
    setExpandedModules((prev) => {
      const next = new Set(prev);
      if (next.has(moduleKey)) {
        next.delete(moduleKey);
      } else {
        next.add(moduleKey);
      }
      return next;
    });
  };

  const filteredGroups = permissionGroups?.filter((group) => {
    if (!search) return true;
    const searchLower = search.toLowerCase();

    // Check module name
    if (group.module_key.toLowerCase().includes(searchLower)) return true;
    if (group.module_title.toLowerCase().includes(searchLower)) return true;

    // Check permissions
    for (const perms of Object.values(group.features)) {
      for (const perm of perms) {
        if (perm.key.toLowerCase().includes(searchLower)) return true;
        if (perm.title.toLowerCase().includes(searchLower)) return true;
      }
    }

    return false;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-stone-400" />
        <input
          type="text"
          placeholder={t('authz.searchPermissions', 'Search permissions...')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
      </div>

      {/* Permission Groups */}
      <div className="space-y-4">
        {filteredGroups?.map((group) => (
          <PermissionGroupCard
            key={group.module_key}
            group={group}
            isExpanded={expandedModules.has(group.module_key)}
            onToggle={() => toggleModule(group.module_key)}
            searchTerm={search}
          />
        ))}
      </div>

      {filteredGroups?.length === 0 && (
        <div className="text-center py-12 text-stone-500 dark:text-stone-400">
          {t('authz.noPermissionsFound', 'No permissions found')}
        </div>
      )}
    </div>
  );
}

interface PermissionGroupCardProps {
  group: PermissionGroup;
  isExpanded: boolean;
  onToggle: () => void;
  searchTerm: string;
}

function PermissionGroupCard({
  group,
  isExpanded,
  onToggle,
  searchTerm,
}: PermissionGroupCardProps) {
  const { t } = useTranslation();
  const totalPermissions = Object.values(group.features).reduce(
    (sum, perms) => sum + perms.length,
    0
  );

  return (
    <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 overflow-hidden">
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-stone-50 dark:hover:bg-stone-700/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="h-5 w-5 text-stone-400" />
          ) : (
            <ChevronRight className="h-5 w-5 text-stone-400" />
          )}
          <Shield className="h-5 w-5 text-teal-500" />
          <div className="text-left">
            <h3 className="font-medium text-stone-900 dark:text-stone-100">
              {group.module_title}
            </h3>
            <p className="text-sm text-stone-500 dark:text-stone-400">
              {group.module_key}
            </p>
          </div>
        </div>
        <span className="text-sm text-stone-500 dark:text-stone-400">
          {totalPermissions} {t('authz.permissions', 'permissions')}
        </span>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-stone-200 dark:border-stone-700">
          {Object.entries(group.features).map(([feature, permissions]) => (
            <div key={feature} className="border-b border-stone-100 dark:border-stone-700 last:border-b-0">
              <div className="px-4 py-2 bg-stone-50 dark:bg-stone-800/50">
                <span className="text-sm font-medium text-stone-700 dark:text-stone-300">
                  {feature}
                </span>
              </div>
              <div className="divide-y divide-stone-100 dark:divide-stone-700">
                {permissions.map((perm) => (
                  <PermissionRow key={perm.key} permission={perm} searchTerm={searchTerm} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface PermissionRowProps {
  permission: Permission;
  searchTerm: string;
}

function PermissionRow({ permission, searchTerm }: PermissionRowProps) {
  const highlight = (text: string) => {
    if (!searchTerm) return text;
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      part.toLowerCase() === searchTerm.toLowerCase() ? (
        <mark key={i} className="bg-yellow-200 dark:bg-yellow-800 rounded px-0.5">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  return (
    <div className="px-4 py-3 flex items-center justify-between hover:bg-stone-50 dark:hover:bg-stone-700/30">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <code className="text-sm font-mono text-teal-600 dark:text-teal-400">
            {highlight(permission.key)}
          </code>
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-300">
            {permission.action}
          </span>
        </div>
        <p className="text-sm text-stone-600 dark:text-stone-400 mt-0.5">
          {highlight(permission.title)}
        </p>
        {permission.description && (
          <p className="text-xs text-stone-500 dark:text-stone-500 mt-0.5">
            {permission.description}
          </p>
        )}
      </div>
    </div>
  );
}

export default PermissionsPage;
