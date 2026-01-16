/**
 * Advanced Settings Page
 *
 * Feature flags, system configuration, and debug settings.
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Flag,
  Settings,
  AlertTriangle,
  Info,
  Loader2,
  RefreshCw,
  Search,
} from 'lucide-react';
import { API_CONFIG } from '@shared/config/api';
import { useFeatureFlags, useUpdateFeatureFlag } from '../hooks';
import { SettingCard } from '../components/SettingCard';
import { SettingRow } from '../components/SettingRow';
import type { FeatureFlag } from '../types';

// Feature flag categories for organization
const FLAG_CATEGORIES = {
  core: {
    label: 'settings.features.core',
    description: 'settings.features.coreDesc',
  },
  experimental: {
    label: 'settings.features.experimental',
    description: 'settings.features.experimentalDesc',
  },
  beta: {
    label: 'settings.features.beta',
    description: 'settings.features.betaDesc',
  },
  deprecated: {
    label: 'settings.features.deprecated',
    description: 'settings.features.deprecatedDesc',
  },
};

export function AdvancedSettingsPage() {
  const { t } = useTranslation();
  const { data: flagsData, isLoading, refetch } = useFeatureFlags();
  const updateFlag = useUpdateFeatureFlag();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const flags = flagsData?.flags || [];

  // Filter flags based on search and category
  const filteredFlags = flags.filter((flag: FeatureFlag) => {
    const matchesSearch =
      !searchQuery ||
      flag.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      flag.description?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCategory = !selectedCategory || flag.category === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  // Group flags by category
  const groupedFlags = filteredFlags.reduce((acc: Record<string, FeatureFlag[]>, flag: FeatureFlag) => {
    const category = flag.category || 'core';
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(flag);
    return acc;
  }, {});

  const handleToggleFlag = async (flag: FeatureFlag) => {
    try {
      await updateFlag.mutateAsync({
        key: flag.key,
        enabled: !flag.enabled,
      });
    } catch (error) {
      console.error('Failed to toggle feature flag:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-teal-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Warning Banner */}
      <div className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
        <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
            {t('settings.advanced.warning', 'Advanced Settings')}
          </p>
          <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
            {t(
              'settings.advanced.warningDesc',
              'These settings are intended for advanced users. Modifying them incorrectly may affect platform stability.'
            )}
          </p>
        </div>
      </div>

      {/* Feature Flags */}
      <SettingCard
        title={t('settings.features.title', 'Feature Flags')}
        description={t('settings.features.description', 'Enable or disable platform features')}
        action={
          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className="p-2 text-stone-500 hover:text-stone-700 dark:hover:text-stone-300"
            title={t('common.refresh', 'Refresh')}
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        }
      >
        {/* Search and Filter */}
        <div className="flex items-center gap-4 py-4 border-b border-stone-100 dark:border-stone-800">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-stone-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('settings.features.searchPlaceholder', 'Search features...')}
              className="w-full pl-10 pr-4 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
            />
          </div>
          <select
            value={selectedCategory || ''}
            onChange={(e) => setSelectedCategory(e.target.value || null)}
            className="px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
          >
            <option value="">{t('settings.features.allCategories', 'All Categories')}</option>
            {Object.entries(FLAG_CATEGORIES).map(([key, cat]) => (
              <option key={key} value={key}>
                {t(cat.label, key)}
              </option>
            ))}
          </select>
        </div>

        {/* Flags List */}
        {Object.keys(groupedFlags).length === 0 ? (
          <div className="py-8 text-center text-stone-500">
            <Flag className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>{t('settings.features.noFlags', 'No feature flags found')}</p>
          </div>
        ) : (
          <div className="divide-y divide-stone-100 dark:divide-stone-800">
            {Object.entries(groupedFlags).map(([category, categoryFlags]) => (
              <div key={category} className="py-4">
                <div className="flex items-center gap-2 mb-3">
                  <Flag className="h-4 w-4 text-stone-400" />
                  <h4 className="text-sm font-medium text-stone-700 dark:text-stone-300">
                    {t(FLAG_CATEGORIES[category as keyof typeof FLAG_CATEGORIES]?.label || category, category)}
                  </h4>
                  <span className="text-xs text-stone-500">({categoryFlags.length})</span>
                </div>
                <div className="space-y-1">
                  {categoryFlags.map((flag: FeatureFlag) => (
                    <div
                      key={flag.key}
                      className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800/50"
                    >
                      <div className="flex-1 pr-4">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-stone-900 dark:text-stone-100 font-mono">
                            {flag.key}
                          </p>
                          {flag.category === 'experimental' && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/20 dark:text-purple-400 rounded-full">
                              {t('settings.features.experimental', 'Experimental')}
                            </span>
                          )}
                          {flag.category === 'beta' && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400 rounded-full">
                              {t('settings.features.beta', 'Beta')}
                            </span>
                          )}
                          {flag.category === 'deprecated' && (
                            <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400 rounded-full">
                              {t('settings.features.deprecated', 'Deprecated')}
                            </span>
                          )}
                        </div>
                        {flag.description && (
                          <p className="text-sm text-stone-500 mt-0.5">{flag.description}</p>
                        )}
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={flag.enabled}
                        onClick={() => handleToggleFlag(flag)}
                        disabled={updateFlag.isPending}
                        className={`
                          relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full
                          border-2 border-transparent transition-colors duration-200 ease-in-out
                          focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2
                          ${updateFlag.isPending ? 'opacity-50 cursor-not-allowed' : ''}
                          ${flag.enabled ? 'bg-teal-600' : 'bg-stone-200 dark:bg-stone-600'}
                        `}
                      >
                        <span
                          className={`
                            pointer-events-none inline-block h-5 w-5 transform rounded-full
                            bg-white shadow ring-0 transition duration-200 ease-in-out
                            ${flag.enabled ? 'translate-x-5' : 'translate-x-0'}
                          `}
                        />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </SettingCard>

      {/* System Information */}
      <SettingCard
        title={t('settings.advanced.systemInfo', 'System Information')}
        description={t('settings.advanced.systemInfoDesc', 'Platform version and environment details')}
      >
        <div className="space-y-3 py-2">
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <Info className="h-5 w-5 text-stone-400" />
              <span className="text-sm text-stone-700 dark:text-stone-300">
                {t('settings.advanced.version', 'Platform Version')}
              </span>
            </div>
            <span className="text-sm font-mono text-stone-900 dark:text-stone-100">
              {import.meta.env.VITE_APP_VERSION || '1.0.0'}
            </span>
          </div>

          <div className="flex items-center justify-between py-2 border-t border-stone-100 dark:border-stone-800">
            <div className="flex items-center gap-3">
              <Settings className="h-5 w-5 text-stone-400" />
              <span className="text-sm text-stone-700 dark:text-stone-300">
                {t('settings.advanced.environment', 'Environment')}
              </span>
            </div>
            <span className="text-sm font-mono text-stone-900 dark:text-stone-100">
              {import.meta.env.MODE}
            </span>
          </div>

          <div className="flex items-center justify-between py-2 border-t border-stone-100 dark:border-stone-800">
            <div className="flex items-center gap-3">
              <Settings className="h-5 w-5 text-stone-400" />
              <span className="text-sm text-stone-700 dark:text-stone-300">
                {t('settings.advanced.apiUrl', 'API Endpoint')}
              </span>
            </div>
            <span className="text-sm font-mono text-stone-900 dark:text-stone-100 truncate max-w-xs">
              {API_CONFIG.BASE_URL}
            </span>
          </div>
        </div>
      </SettingCard>

      {/* Debug Settings */}
      {import.meta.env.DEV && (
        <SettingCard
          title={t('settings.advanced.debug', 'Debug Settings')}
          description={t('settings.advanced.debugDesc', 'Development and debugging options')}
        >
          <div className="flex items-start gap-3 p-3 bg-stone-50 dark:bg-stone-800 rounded-lg mb-4">
            <Info className="h-5 w-5 text-stone-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-stone-600 dark:text-stone-400">
              {t(
                'settings.advanced.debugNote',
                'These options are only available in development mode and will not appear in production.'
              )}
            </p>
          </div>

          <SettingRow
            title={t('settings.advanced.enableLogging', 'Verbose Logging')}
            description={t('settings.advanced.enableLoggingDesc', 'Log detailed API requests and responses')}
            checked={localStorage.getItem('debug_verbose_logging') === 'true'}
            onChange={(checked) => {
              localStorage.setItem('debug_verbose_logging', String(checked));
              window.location.reload();
            }}
          />

          <SettingRow
            title={t('settings.advanced.mockData', 'Use Mock Data')}
            description={t('settings.advanced.mockDataDesc', 'Use mock data instead of API calls')}
            checked={localStorage.getItem('debug_mock_data') === 'true'}
            onChange={(checked) => {
              localStorage.setItem('debug_mock_data', String(checked));
              window.location.reload();
            }}
          />

          <div className="pt-4 border-t border-stone-100 dark:border-stone-800">
            <button
              onClick={() => {
                localStorage.clear();
                sessionStorage.clear();
                window.location.reload();
              }}
              className="px-4 py-2 text-sm font-medium text-red-600 hover:text-red-700 border border-red-300 hover:border-red-400 rounded-lg transition-colors"
            >
              {t('settings.advanced.clearStorage', 'Clear Local Storage')}
            </button>
          </div>
        </SettingCard>
      )}

      {/* Danger Zone */}
      <SettingCard
        title={t('settings.advanced.dangerZone', 'Danger Zone')}
        description={t('settings.advanced.dangerZoneDesc', 'Irreversible and destructive actions')}
      >
        <div className="space-y-4 py-2">
          <div className="flex items-center justify-between p-4 border border-red-200 dark:border-red-800 rounded-lg bg-red-50 dark:bg-red-900/10">
            <div>
              <p className="text-sm font-medium text-red-800 dark:text-red-200">
                {t('settings.advanced.resetSettings', 'Reset All Settings')}
              </p>
              <p className="text-sm text-red-600 dark:text-red-400 mt-0.5">
                {t('settings.advanced.resetSettingsDesc', 'Reset all settings to their default values')}
              </p>
            </div>
            <button
              onClick={() => {
                if (
                  confirm(
                    t(
                      'settings.advanced.confirmReset',
                      'Are you sure you want to reset all settings? This action cannot be undone.'
                    )
                  )
                ) {
                  // Call reset API
                  console.log('Reset settings requested');
                }
              }}
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
            >
              {t('settings.advanced.reset', 'Reset')}
            </button>
          </div>
        </div>
      </SettingCard>
    </div>
  );
}

export default AdvancedSettingsPage;
