/**
 * Authentication Settings Page
 *
 * Manages authentication methods, SSO providers, and session settings.
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Trash2, Edit2, AlertTriangle, Check } from 'lucide-react';
import {
  useAuthPolicy,
  useUpdateAuthPolicy,
  useSSOProviders,
  useCreateSSOProvider,
  useDeleteSSOProvider,
} from '../hooks';
import type { AuthDomain, SSOProviderType, SSOProvider } from '../types';
import { SettingCard } from '../components/SettingCard';
import { SettingRow } from '../components/SettingRow';
import { SSOProviderModal } from '../components/SSOProviderModal';

type AuthTab = 'admin' | 'members' | 'webapp';

const authTabs: { key: AuthTab; label: string; domain: AuthDomain }[] = [
  { key: 'admin', label: 'settings.auth.admin', domain: 'admin' },
  { key: 'members', label: 'settings.auth.members', domain: 'members' },
  { key: 'webapp', label: 'settings.auth.webapp', domain: 'webapp' },
];

export function AuthSettingsPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<AuthTab>('admin');
  const [showProviderModal, setShowProviderModal] = useState(false);
  const [selectedProviderType, setSelectedProviderType] = useState<SSOProviderType | null>(null);
  const [editingProvider, setEditingProvider] = useState<SSOProvider | null>(null);

  const currentDomain = authTabs.find((tab) => tab.key === activeTab)?.domain || 'admin';

  const { data: authPolicy, isLoading: isLoadingPolicy } = useAuthPolicy(currentDomain);
  const updatePolicy = useUpdateAuthPolicy(currentDomain);

  const { data: ssoData, isLoading: isLoadingSSO } = useSSOProviders(currentDomain);
  const createProvider = useCreateSSOProvider(currentDomain);
  const deleteProvider = useDeleteSSOProvider(currentDomain);

  const handleToggle = async (key: string, value: boolean) => {
    if (!authPolicy) return;

    try {
      await updatePolicy.mutateAsync({
        [key]: value,
        // If disabling all methods, require confirmation
        confirm_risk:
          key === 'email_password_enabled' &&
          !value &&
          !authPolicy.sso_enabled &&
          !authPolicy.email_code_enabled,
      });
    } catch (error: any) {
      console.error('Failed to update auth policy:', error);
      alert(error.response?.data?.detail || 'Failed to update setting');
    }
  };

  const handleSessionTimeoutChange = async (days: number) => {
    try {
      await updatePolicy.mutateAsync({ session_timeout_days: days });
    } catch (error: any) {
      console.error('Failed to update session timeout:', error);
    }
  };

  const handleCreateProvider = (type: SSOProviderType) => {
    setSelectedProviderType(type);
    setEditingProvider(null);
    setShowProviderModal(true);
  };

  const handleEditProvider = (provider: SSOProvider) => {
    setSelectedProviderType(provider.provider_type);
    setEditingProvider(provider);
    setShowProviderModal(true);
  };

  const handleDeleteProvider = async (provider: SSOProvider) => {
    if (!confirm(t('settings.sso.confirmDelete', `Are you sure you want to delete "${provider.display_name || provider.name}"?`))) {
      return;
    }
    try {
      await deleteProvider.mutateAsync(provider.id);
    } catch (error) {
      console.error('Failed to delete provider:', error);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Sub-tabs for Admin/Members/Webapp */}
      <div className="flex space-x-1 bg-stone-100 dark:bg-stone-800 p-1 rounded-lg w-fit">
        {authTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === tab.key
                ? 'bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 shadow-sm'
                : 'text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100'
            }`}
          >
            {t(tab.label)}
          </button>
        ))}
      </div>

      {/* Login Methods */}
      <SettingCard
        title={t('settings.auth.loginMethods', 'Login Methods')}
        description={t('settings.auth.loginMethodsDesc', 'Configure how users can authenticate')}
      >
        <SettingRow
          title={t('settings.auth.emailPassword', 'Email & Password')}
          description={t('settings.auth.emailPasswordDesc', 'Allow login with email and password')}
          checked={authPolicy?.email_password_enabled ?? true}
          onChange={(checked) => handleToggle('email_password_enabled', checked)}
          disabled={isLoadingPolicy || updatePolicy.isPending}
        />

        {activeTab !== 'admin' && (
          <SettingRow
            title={t('settings.auth.emailCode', 'Email & Verification Code')}
            description={t('settings.auth.emailCodeDesc', 'Allow login with email verification code')}
            checked={authPolicy?.email_code_enabled ?? false}
            onChange={(checked) => handleToggle('email_code_enabled', checked)}
            disabled={isLoadingPolicy || updatePolicy.isPending}
          />
        )}

        <SettingRow
          title={t('settings.auth.sso', 'Single Sign-On (SSO)')}
          description={t('settings.auth.ssoDesc', 'Allow login via external identity providers')}
          checked={authPolicy?.sso_enabled ?? false}
          onChange={(checked) => handleToggle('sso_enabled', checked)}
          disabled={isLoadingPolicy || updatePolicy.isPending}
        />
      </SettingCard>

      {/* SSO Providers */}
      {authPolicy?.sso_enabled && (
        <SettingCard
          title={t('settings.sso.providers', 'SSO Identity Providers')}
          description={t('settings.sso.providersDesc', 'Manage external authentication providers')}
          action={
            <div className="relative group">
              <button className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors">
                <Plus className="h-4 w-4" />
                {t('settings.sso.addProvider', 'Add Provider')}
              </button>
              <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-stone-800 rounded-lg shadow-lg border border-stone-200 dark:border-stone-700 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                <button
                  onClick={() => handleCreateProvider('oidc')}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-stone-100 dark:hover:bg-stone-700 rounded-t-lg"
                >
                  {t('settings.sso.newOIDC', 'New OIDC Provider')}
                </button>
                <button
                  onClick={() => handleCreateProvider('oauth2')}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-stone-100 dark:hover:bg-stone-700"
                >
                  {t('settings.sso.newOAuth2', 'New OAuth2 Provider')}
                </button>
                <button
                  onClick={() => handleCreateProvider('saml')}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-stone-100 dark:hover:bg-stone-700 rounded-b-lg"
                >
                  {t('settings.sso.newSAML', 'New SAML Provider')}
                </button>
              </div>
            </div>
          }
        >
          {isLoadingSSO ? (
            <div className="py-8 text-center text-stone-500">
              {t('common.loading', 'Loading...')}
            </div>
          ) : ssoData?.providers.length === 0 ? (
            <div className="py-8 text-center text-stone-500">
              <p>{t('settings.sso.noProviders', 'No SSO providers configured')}</p>
              <p className="text-sm mt-1">
                {t('settings.sso.noProvidersHint', 'Click "Add Provider" to configure SSO')}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {ssoData?.providers.map((provider) => (
                <div
                  key={provider.id}
                  className="flex items-center justify-between p-3 bg-stone-50 dark:bg-stone-800 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-3 h-3 rounded-full ${
                        provider.enabled ? 'bg-green-500' : 'bg-stone-300'
                      }`}
                    />
                    <div>
                      <p className="font-medium text-stone-900 dark:text-stone-100">
                        {provider.display_name || provider.name}
                      </p>
                      <p className="text-sm text-stone-500">
                        {provider.provider_type.toUpperCase()}
                        {provider.enabled && (
                          <span className="ml-2 text-green-600">
                            <Check className="inline h-3 w-3" /> {t('common.enabled', 'Enabled')}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleEditProvider(provider)}
                      className="p-2 text-stone-500 hover:text-stone-700 dark:hover:text-stone-300"
                      title={t('common.edit', 'Edit')}
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteProvider(provider)}
                      className="p-2 text-red-500 hover:text-red-700"
                      title={t('common.delete', 'Delete')}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SettingCard>
      )}

      {/* Session Settings */}
      <SettingCard
        title={t('settings.auth.session', 'Session Settings')}
        description={t('settings.auth.sessionDesc', 'Configure session timeout and behavior')}
      >
        <div className="flex items-center justify-between py-3">
          <div>
            <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
              {t('settings.auth.sessionTimeout', 'Session Timeout')}
            </p>
            <p className="text-sm text-stone-500">
              {t('settings.auth.sessionTimeoutDesc', 'Time before users need to re-authenticate')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={1}
              max={365}
              value={authPolicy?.session_timeout_days ?? 1}
              onChange={(e) => handleSessionTimeoutChange(parseInt(e.target.value, 10))}
              className="w-20 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
              disabled={isLoadingPolicy || updatePolicy.isPending}
            />
            <span className="text-sm text-stone-500">{t('common.days', 'days')}</span>
          </div>
        </div>
      </SettingCard>

      {/* Members-specific settings */}
      {activeTab === 'members' && (
        <SettingCard
          title={t('settings.auth.signup', 'Workspace Registration')}
          description={t('settings.auth.signupDesc', 'Configure how users can join the platform')}
        >
          <SettingRow
            title={t('settings.auth.selfSignup', 'Allow Self-Registration')}
            description={t('settings.auth.selfSignupDesc', 'Users can create accounts without invitation')}
            checked={authPolicy?.self_signup_enabled ?? false}
            onChange={(checked) => handleToggle('self_signup_enabled', checked)}
            disabled={isLoadingPolicy || updatePolicy.isPending}
          />

          {authPolicy?.self_signup_enabled && (
            <SettingRow
              title={t('settings.auth.autoCreateSpace', 'Auto-create Personal Space')}
              description={t('settings.auth.autoCreateSpaceDesc', 'Automatically create a workspace for new users')}
              checked={authPolicy?.signup_auto_create_personal_space ?? false}
              onChange={(checked) => handleToggle('signup_auto_create_personal_space', checked)}
              disabled={isLoadingPolicy || updatePolicy.isPending}
            />
          )}
        </SettingCard>
      )}

      {/* Admin-specific settings */}
      {activeTab === 'admin' && authPolicy?.sso_enabled && (
        <SettingCard
          title={t('settings.auth.autoCreateAdmin', 'Auto-Create Administrator')}
          description={t('settings.auth.autoCreateAdminDesc', 'Automatically create admin accounts from SSO')}
        >
          <div className="flex items-start gap-3 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg mb-4">
            <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-amber-800 dark:text-amber-200">
              {t(
                'settings.auth.autoCreateAdminWarning',
                'This is a security-sensitive setting. Only enable if you trust the configured SSO providers and have set email domain restrictions.'
              )}
            </p>
          </div>

          <SettingRow
            title={t('settings.auth.autoCreateAdminToggle', 'Auto-Create Admin on First SSO Login')}
            description={t(
              'settings.auth.autoCreateAdminToggleDesc',
              'Create administrator account when user first logs in via SSO'
            )}
            checked={authPolicy?.auto_create_admin_on_first_sso ?? false}
            onChange={(checked) => handleToggle('auto_create_admin_on_first_sso', checked)}
            disabled={isLoadingPolicy || updatePolicy.isPending}
          />
        </SettingCard>
      )}

      {/* SSO Provider Modal */}
      {showProviderModal && selectedProviderType && (
        <SSOProviderModal
          providerType={selectedProviderType}
          domain={currentDomain}
          existingProvider={editingProvider}
          onClose={() => {
            setShowProviderModal(false);
            setSelectedProviderType(null);
            setEditingProvider(null);
          }}
        />
      )}
    </div>
  );
}

export default AuthSettingsPage;
