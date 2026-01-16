/**
 * Modules Management Page
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Layers, ToggleLeft, ToggleRight, RefreshCw } from 'lucide-react';
import { authzClient } from '../api/authzClient';
import { RequireSuperAdmin, RequirePermission } from '../components/PermissionGate';
import type { Module, TenantModuleSetting } from '../api/authzTypes';

export function ModulesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: modules, isLoading: modulesLoading } = useQuery({
    queryKey: ['modules'],
    queryFn: () => authzClient.listModules(),
  });

  const { data: tenantSettings, isLoading: settingsLoading } = useQuery({
    queryKey: ['tenant-modules'],
    queryFn: () => authzClient.getTenantModuleSettings(),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ moduleKey, enabled }: { moduleKey: string; enabled: boolean }) =>
      authzClient.updateTenantModuleSetting(moduleKey, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-modules'] });
      queryClient.invalidateQueries({ queryKey: ['authz', 'me'] });
    },
  });

  const syncMutation = useMutation({
    mutationFn: () => authzClient.syncManifest(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['modules'] });
      queryClient.invalidateQueries({ queryKey: ['permissions'] });
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
  });

  const isLoading = modulesLoading || settingsLoading;

  // Create a map of tenant settings for quick lookup
  const settingsMap = new Map(
    tenantSettings?.map((s) => [s.module_key, s.enabled]) || []
  );

  const getModuleEnabled = (module: Module): boolean => {
    return settingsMap.get(module.module_key) ?? module.default_enabled;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Actions */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-medium text-stone-900 dark:text-stone-100">
            {t('authz.modules.title', 'Module Settings')}
          </h2>
          <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
            {t('authz.modules.description', 'Enable or disable platform modules for your tenant')}
          </p>
        </div>

        <RequireSuperAdmin>
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
            {t('authz.modules.syncManifest', 'Sync Manifest')}
          </button>
        </RequireSuperAdmin>
      </div>

      {/* Module List */}
      <div className="grid gap-4 md:grid-cols-2">
        {modules?.items
          .sort((a, b) => a.order - b.order)
          .map((module) => (
            <ModuleCard
              key={module.module_key}
              module={module}
              enabled={getModuleEnabled(module)}
              onToggle={(enabled) =>
                toggleMutation.mutate({ moduleKey: module.module_key, enabled })
              }
              isToggling={toggleMutation.isPending}
            />
          ))}
      </div>
    </div>
  );
}

interface ModuleCardProps {
  module: Module;
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  isToggling: boolean;
}

function ModuleCard({ module, enabled, onToggle, isToggling }: ModuleCardProps) {
  const { t } = useTranslation();

  return (
    <div
      className={`bg-white dark:bg-stone-800 rounded-lg border p-4 transition-colors ${
        enabled
          ? 'border-teal-200 dark:border-teal-800'
          : 'border-stone-200 dark:border-stone-700'
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div
            className={`p-2 rounded-lg ${
              enabled
                ? 'bg-teal-100 dark:bg-teal-900/50 text-teal-600 dark:text-teal-400'
                : 'bg-stone-100 dark:bg-stone-700 text-stone-500 dark:text-stone-400'
            }`}
          >
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-medium text-stone-900 dark:text-stone-100">
              {module.title}
            </h3>
            <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
              {module.module_key}
            </p>
            {module.description && (
              <p className="text-sm text-stone-600 dark:text-stone-400 mt-2">
                {module.description}
              </p>
            )}
          </div>
        </div>

        <RequirePermission permission="security.module.manage">
          <button
            onClick={() => onToggle(!enabled)}
            disabled={isToggling}
            className={`p-1 rounded transition-colors ${
              enabled
                ? 'text-teal-600 hover:text-teal-700 dark:text-teal-400'
                : 'text-stone-400 hover:text-stone-500'
            }`}
          >
            {enabled ? (
              <ToggleRight className="h-8 w-8" />
            ) : (
              <ToggleLeft className="h-8 w-8" />
            )}
          </button>
        </RequirePermission>
      </div>

      {/* Default indicator */}
      <div className="mt-3 pt-3 border-t border-stone-100 dark:border-stone-700">
        <span className="text-xs text-stone-500 dark:text-stone-500">
          {t('authz.modules.default', 'Default')}: {module.default_enabled ? t('authz.enabled', 'Enabled') : t('authz.disabled', 'Disabled')}
        </span>
      </div>
    </div>
  );
}

export default ModulesPage;
