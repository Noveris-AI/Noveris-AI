/**
 * SSO Provider Modal Component
 *
 * Modal for creating/editing SSO providers (OIDC, OAuth2, SAML).
 */

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Copy, Check, ExternalLink } from 'lucide-react';
import { useCreateSSOProvider, useUpdateSSOProvider } from '../hooks';
import type { AuthDomain, SSOProviderType, SSOProvider } from '../types';

interface SSOProviderModalProps {
  providerType: SSOProviderType;
  domain: AuthDomain;
  existingProvider?: SSOProvider | null;
  onClose: () => void;
}

export function SSOProviderModal({
  providerType,
  domain,
  existingProvider,
  onClose,
}: SSOProviderModalProps) {
  const { t } = useTranslation();
  const isEditing = !!existingProvider;

  const createProvider = useCreateSSOProvider(domain);
  const updateProvider = useUpdateSSOProvider(domain);

  // Form state
  const [name, setName] = useState(existingProvider?.name || '');
  const [displayName, setDisplayName] = useState(existingProvider?.display_name || '');
  const [enabled, setEnabled] = useState(existingProvider?.enabled || false);

  // OIDC fields
  const [issuerUrl, setIssuerUrl] = useState(
    existingProvider?.config?.issuer_or_discovery_url as string || ''
  );
  const [clientId, setClientId] = useState(
    existingProvider?.config?.client_id as string || ''
  );
  const [clientSecret, setClientSecret] = useState('');
  const [scopes, setScopes] = useState(
    (existingProvider?.config?.scopes as string) || 'openid profile email'
  );
  const [usePkce, setUsePkce] = useState(
    (existingProvider?.config?.use_pkce as boolean) ?? true
  );

  // OAuth2 fields
  const [authEndpoint, setAuthEndpoint] = useState(
    existingProvider?.config?.authorization_endpoint as string || ''
  );
  const [tokenEndpoint, setTokenEndpoint] = useState(
    existingProvider?.config?.token_endpoint as string || ''
  );
  const [userinfoEndpoint, setUserinfoEndpoint] = useState(
    existingProvider?.config?.userinfo_endpoint as string || ''
  );

  // SAML fields
  const [idpSsoUrl, setIdpSsoUrl] = useState(
    existingProvider?.config?.idp_sso_url as string || ''
  );
  const [x509Cert, setX509Cert] = useState('');

  // Copy state
  const [copied, setCopied] = useState<string | null>(null);

  // Callback URL (read-only)
  const callbackUrl = existingProvider?.callback_url ||
    `${window.location.origin}/api/v1/sso/${domain}/${providerType}/<provider_id>/callback`;
  const acsUrl = existingProvider?.acs_url ||
    `${window.location.origin}/api/v1/sso/${domain}/saml/<provider_id>/acs`;

  const handleCopy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    let config: Record<string, unknown> = {};
    let secrets: Record<string, unknown> = {};

    if (providerType === 'oidc') {
      config = {
        issuer_or_discovery_url: issuerUrl,
        client_id: clientId,
        scopes,
        use_pkce: usePkce,
      };
      if (clientSecret) {
        secrets.client_secret = clientSecret;
      }
    } else if (providerType === 'oauth2') {
      config = {
        authorization_endpoint: authEndpoint,
        token_endpoint: tokenEndpoint,
        userinfo_endpoint: userinfoEndpoint,
        client_id: clientId,
        scopes,
        use_pkce: usePkce,
      };
      if (clientSecret) {
        secrets.client_secret = clientSecret;
      }
    } else if (providerType === 'saml') {
      config = {
        idp_sso_url: idpSsoUrl,
      };
      if (x509Cert) {
        secrets.x509_cert_pem = x509Cert;
      }
    }

    try {
      if (isEditing && existingProvider) {
        await updateProvider.mutateAsync({
          id: existingProvider.id,
          data: {
            name,
            display_name: displayName || undefined,
            enabled,
            config,
            secrets: Object.keys(secrets).length > 0 ? secrets : undefined,
          },
        });
      } else {
        await createProvider.mutateAsync({
          provider_type: providerType,
          name,
          display_name: displayName || undefined,
          enabled,
          config,
          secrets: Object.keys(secrets).length > 0 ? secrets : undefined,
        });
      }
      onClose();
    } catch (error: any) {
      console.error('Failed to save provider:', error);
      alert(error.response?.data?.detail || 'Failed to save provider');
    }
  };

  const getTitle = () => {
    const type = providerType.toUpperCase();
    return isEditing
      ? t('settings.sso.editProvider', `Edit ${type} Provider`)
      : t('settings.sso.createProvider', `Create ${type} Provider`);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/50 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative w-full max-w-lg bg-white dark:bg-stone-900 rounded-xl shadow-xl">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-stone-200 dark:border-stone-700">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
              {getTitle()}
            </h2>
            <button
              onClick={onClose}
              className="p-1 text-stone-500 hover:text-stone-700 dark:hover:text-stone-300"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            <div className="px-6 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
              {/* Basic Info */}
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  {t('settings.sso.providerName', 'Provider Name')} *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="e.g., okta, azure-ad"
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  {t('settings.sso.displayName', 'Display Name')}
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g., Login with Okta"
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                />
              </div>

              {/* OIDC Fields */}
              {providerType === 'oidc' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.issuerUrl', 'Discovery URL / Issuer')} *
                    </label>
                    <input
                      type="url"
                      value={issuerUrl}
                      onChange={(e) => setIssuerUrl(e.target.value)}
                      required
                      placeholder="https://example.okta.com/.well-known/openid-configuration"
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    />
                    <p className="mt-1 text-xs text-stone-500">
                      {t('settings.sso.issuerUrlHint', 'The OIDC discovery document URL or issuer base URL')}
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.clientId', 'Client ID')} *
                    </label>
                    <input
                      type="text"
                      value={clientId}
                      onChange={(e) => setClientId(e.target.value)}
                      required
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.clientSecret', 'Client Secret')}
                      {isEditing && (
                        <span className="text-stone-500 font-normal ml-1">
                          ({t('settings.sso.leaveBlank', 'leave blank to keep existing')})
                        </span>
                      )}
                    </label>
                    <input
                      type="password"
                      value={clientSecret}
                      onChange={(e) => setClientSecret(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-stone-700 dark:text-stone-300">
                        {t('settings.sso.usePkce', 'Use PKCE')}
                      </p>
                      <p className="text-xs text-stone-500">
                        {t('settings.sso.usePkceHint', 'Recommended for enhanced security')}
                      </p>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={usePkce}
                      onClick={() => setUsePkce(!usePkce)}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                        usePkce ? 'bg-teal-600' : 'bg-stone-200 dark:bg-stone-600'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${
                          usePkce ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>

                  {/* Callback URL (Read-only) */}
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.callbackUrl', 'Callback URL')}
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={callbackUrl}
                        readOnly
                        className="flex-1 px-3 py-2 border border-stone-200 dark:border-stone-700 rounded-lg bg-stone-50 dark:bg-stone-800 text-stone-600 dark:text-stone-400 text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => handleCopy(callbackUrl, 'callback')}
                        className="p-2 text-stone-500 hover:text-stone-700"
                      >
                        {copied === 'callback' ? (
                          <Check className="h-4 w-4 text-green-500" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                    <p className="mt-1 text-xs text-stone-500">
                      {t('settings.sso.callbackUrlHint', 'Configure this URL in your identity provider')}
                    </p>
                  </div>
                </>
              )}

              {/* OAuth2 Fields */}
              {providerType === 'oauth2' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.authEndpoint', 'Authorization Endpoint')} *
                    </label>
                    <input
                      type="url"
                      value={authEndpoint}
                      onChange={(e) => setAuthEndpoint(e.target.value)}
                      required
                      placeholder="https://provider.com/oauth/authorize"
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.tokenEndpoint', 'Token Endpoint')} *
                    </label>
                    <input
                      type="url"
                      value={tokenEndpoint}
                      onChange={(e) => setTokenEndpoint(e.target.value)}
                      required
                      placeholder="https://provider.com/oauth/token"
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.userinfoEndpoint', 'UserInfo Endpoint')} *
                    </label>
                    <input
                      type="url"
                      value={userinfoEndpoint}
                      onChange={(e) => setUserinfoEndpoint(e.target.value)}
                      required
                      placeholder="https://provider.com/oauth/userinfo"
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.clientId', 'Client ID')} *
                    </label>
                    <input
                      type="text"
                      value={clientId}
                      onChange={(e) => setClientId(e.target.value)}
                      required
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.clientSecret', 'Client Secret')}
                    </label>
                    <input
                      type="password"
                      value={clientSecret}
                      onChange={(e) => setClientSecret(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.scopes', 'Scopes')}
                    </label>
                    <input
                      type="text"
                      value={scopes}
                      onChange={(e) => setScopes(e.target.value)}
                      placeholder="profile email"
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    />
                  </div>

                  {/* Callback URL */}
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.callbackUrl', 'Callback URL')}
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={callbackUrl}
                        readOnly
                        className="flex-1 px-3 py-2 border border-stone-200 dark:border-stone-700 rounded-lg bg-stone-50 dark:bg-stone-800 text-stone-600 dark:text-stone-400 text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => handleCopy(callbackUrl, 'callback')}
                        className="p-2 text-stone-500 hover:text-stone-700"
                      >
                        {copied === 'callback' ? (
                          <Check className="h-4 w-4 text-green-500" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </>
              )}

              {/* SAML Fields */}
              {providerType === 'saml' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.idpSsoUrl', 'IdP SSO URL')} *
                    </label>
                    <input
                      type="url"
                      value={idpSsoUrl}
                      onChange={(e) => setIdpSsoUrl(e.target.value)}
                      required
                      placeholder="https://idp.example.com/saml/sso"
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.x509Cert', 'X509 Signing Certificate')} *
                    </label>
                    <textarea
                      value={x509Cert}
                      onChange={(e) => setX509Cert(e.target.value)}
                      required={!isEditing}
                      rows={6}
                      placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent font-mono text-xs"
                    />
                    <p className="mt-1 text-xs text-stone-500">
                      {t('settings.sso.x509CertHint', 'Paste the X509 certificate in PEM format')}
                    </p>
                  </div>

                  {/* ACS URL */}
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.sso.acsUrl', 'ACS URL (Assertion Consumer Service)')}
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={acsUrl}
                        readOnly
                        className="flex-1 px-3 py-2 border border-stone-200 dark:border-stone-700 rounded-lg bg-stone-50 dark:bg-stone-800 text-stone-600 dark:text-stone-400 text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => handleCopy(acsUrl, 'acs')}
                        className="p-2 text-stone-500 hover:text-stone-700"
                      >
                        {copied === 'acs' ? (
                          <Check className="h-4 w-4 text-green-500" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                    <p className="mt-1 text-xs text-stone-500">
                      {t('settings.sso.acsUrlHint', 'Configure this URL in your identity provider')}
                    </p>
                  </div>
                </>
              )}

              {/* Enable Toggle */}
              <div className="flex items-center justify-between pt-2">
                <div>
                  <p className="text-sm font-medium text-stone-700 dark:text-stone-300">
                    {t('settings.sso.enableProvider', 'Enable Provider')}
                  </p>
                  <p className="text-xs text-stone-500">
                    {t('settings.sso.enableProviderHint', 'Show this provider on the login page')}
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={enabled}
                  onClick={() => setEnabled(!enabled)}
                  className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                    enabled ? 'bg-teal-600' : 'bg-stone-200 dark:bg-stone-600'
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${
                      enabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-stone-200 dark:border-stone-700">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-stone-700 dark:text-stone-300 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg transition-colors"
              >
                {t('common.cancel', 'Cancel')}
              </button>
              <button
                type="submit"
                disabled={createProvider.isPending || updateProvider.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors disabled:opacity-50"
              >
                {createProvider.isPending || updateProvider.isPending
                  ? t('common.saving', 'Saving...')
                  : isEditing
                  ? t('common.save', 'Save')
                  : t('common.create', 'Create')}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
