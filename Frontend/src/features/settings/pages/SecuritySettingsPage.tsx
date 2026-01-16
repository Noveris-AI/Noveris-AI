/**
 * Security Settings Page
 *
 * Manages security policies: password rules, IP access control, audit logging.
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Shield,
  Key,
  Globe,
  FileText,
  Plus,
  Trash2,
  AlertTriangle,
  Loader2,
  Download,
  RefreshCw,
} from 'lucide-react';
import { useSecurityPolicy, useUpdateSecurityPolicy, useAuditLogs } from '../hooks';
import { SettingCard } from '../components/SettingCard';
import { SettingRow } from '../components/SettingRow';
import type { AuditLog } from '../types';

export function SecuritySettingsPage() {
  const { t } = useTranslation();
  const { data: policy, isLoading } = useSecurityPolicy();
  const updatePolicy = useUpdateSecurityPolicy();
  const { data: auditData, isLoading: isLoadingAudit, refetch: refetchAudit } = useAuditLogs({
    limit: 50,
  });

  // IP allowlist state
  const [newAllowedIP, setNewAllowedIP] = useState('');
  const [newBlockedIP, setNewBlockedIP] = useState('');
  const [newEgressDomain, setNewEgressDomain] = useState('');

  // Password policy changes
  const [hasChanges, setHasChanges] = useState(false);
  const [localPolicy, setLocalPolicy] = useState<{
    min_password_length?: number;
    require_uppercase?: boolean;
    require_lowercase?: boolean;
    require_numbers?: boolean;
    require_special_chars?: boolean;
    password_expiry_days?: number;
    max_failed_attempts?: number;
    lockout_duration_minutes?: number;
  }>({});

  const handleToggle = async (key: string, value: boolean) => {
    try {
      await updatePolicy.mutateAsync({ [key]: value });
    } catch (error) {
      console.error('Failed to update security policy:', error);
    }
  };

  const handleLocalChange = (key: string, value: number | boolean) => {
    setLocalPolicy((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleSavePasswordPolicy = async () => {
    try {
      await updatePolicy.mutateAsync(localPolicy);
      setHasChanges(false);
      setLocalPolicy({});
    } catch (error) {
      console.error('Failed to update password policy:', error);
    }
  };

  const handleAddIP = async (type: 'allowed' | 'blocked') => {
    const ip = type === 'allowed' ? newAllowedIP : newBlockedIP;
    if (!ip.trim()) return;

    // Basic IP/CIDR validation
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/;
    if (!ipRegex.test(ip.trim())) {
      alert(t('settings.security.invalidIP', 'Invalid IP address or CIDR format'));
      return;
    }

    const currentList =
      type === 'allowed'
        ? policy?.ip_allowlist || []
        : policy?.ip_blocklist || [];

    try {
      await updatePolicy.mutateAsync({
        [type === 'allowed' ? 'ip_allowlist' : 'ip_blocklist']: [
          ...currentList,
          ip.trim(),
        ],
      });
      type === 'allowed' ? setNewAllowedIP('') : setNewBlockedIP('');
    } catch (error) {
      console.error('Failed to add IP:', error);
    }
  };

  const handleRemoveIP = async (type: 'allowed' | 'blocked', ip: string) => {
    const currentList =
      type === 'allowed'
        ? policy?.ip_allowlist || []
        : policy?.ip_blocklist || [];

    try {
      await updatePolicy.mutateAsync({
        [type === 'allowed' ? 'ip_allowlist' : 'ip_blocklist']: currentList.filter(
          (i) => i !== ip
        ),
      });
    } catch (error) {
      console.error('Failed to remove IP:', error);
    }
  };

  const handleAddEgressDomain = async () => {
    if (!newEgressDomain.trim()) return;

    const currentList = policy?.egress_allowed_domains || [];

    try {
      await updatePolicy.mutateAsync({
        egress_allowed_domains: [...currentList, newEgressDomain.trim()],
      });
      setNewEgressDomain('');
    } catch (error) {
      console.error('Failed to add egress domain:', error);
    }
  };

  const handleRemoveEgressDomain = async (domain: string) => {
    const currentList = policy?.egress_allowed_domains || [];

    try {
      await updatePolicy.mutateAsync({
        egress_allowed_domains: currentList.filter((d) => d !== domain),
      });
    } catch (error) {
      console.error('Failed to remove egress domain:', error);
    }
  };

  const handleExportAuditLogs = () => {
    if (!auditData?.logs) return;

    const csv = [
      ['Timestamp', 'Actor', 'Action', 'Resource', 'IP Address', 'Details'].join(','),
      ...auditData.logs.map((log: AuditLog) =>
        [
          log.created_at,
          log.actor_email || log.actor_id,
          log.action,
          log.resource_type,
          log.ip_address || '',
          JSON.stringify(log.changes || {}).replace(/,/g, ';'),
        ].join(',')
      ),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-logs-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-teal-600" />
      </div>
    );
  }

  const displayPolicy = {
    min_password_length: localPolicy.min_password_length ?? policy?.min_password_length ?? 8,
    require_uppercase: localPolicy.require_uppercase ?? policy?.require_uppercase ?? true,
    require_lowercase: localPolicy.require_lowercase ?? policy?.require_lowercase ?? true,
    require_numbers: localPolicy.require_numbers ?? policy?.require_numbers ?? true,
    require_special_chars: localPolicy.require_special_chars ?? policy?.require_special_chars ?? false,
    password_expiry_days: localPolicy.password_expiry_days ?? policy?.password_expiry_days ?? 0,
    max_failed_attempts: localPolicy.max_failed_attempts ?? policy?.max_failed_attempts ?? 5,
    lockout_duration_minutes: localPolicy.lockout_duration_minutes ?? policy?.lockout_duration_minutes ?? 30,
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Password Policy */}
      <SettingCard
        title={t('settings.security.passwordPolicy', 'Password Policy')}
        description={t('settings.security.passwordPolicyDesc', 'Password strength requirements')}
        action={
          hasChanges && (
            <button
              onClick={handleSavePasswordPolicy}
              disabled={updatePolicy.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {updatePolicy.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                t('common.saveChanges', 'Save Changes')
              )}
            </button>
          )
        }
      >
        {/* Minimum Length */}
        <div className="flex items-center justify-between py-3">
          <div className="flex items-center gap-3">
            <Key className="h-5 w-5 text-stone-400" />
            <div>
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.security.minLength', 'Minimum Password Length')}
              </p>
            </div>
          </div>
          <input
            type="number"
            min={6}
            max={32}
            value={displayPolicy.min_password_length}
            onChange={(e) => handleLocalChange('min_password_length', parseInt(e.target.value, 10))}
            className="w-20 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
          />
        </div>

        {/* Character requirements */}
        <SettingRow
          title={t('settings.security.requireUppercase', 'Require Uppercase Letter')}
          checked={displayPolicy.require_uppercase}
          onChange={(checked) => handleLocalChange('require_uppercase', checked)}
          disabled={updatePolicy.isPending}
        />
        <SettingRow
          title={t('settings.security.requireLowercase', 'Require Lowercase Letter')}
          checked={displayPolicy.require_lowercase}
          onChange={(checked) => handleLocalChange('require_lowercase', checked)}
          disabled={updatePolicy.isPending}
        />
        <SettingRow
          title={t('settings.security.requireNumbers', 'Require Numbers')}
          checked={displayPolicy.require_numbers}
          onChange={(checked) => handleLocalChange('require_numbers', checked)}
          disabled={updatePolicy.isPending}
        />
        <SettingRow
          title={t('settings.security.requireSpecial', 'Require Special Characters')}
          checked={displayPolicy.require_special_chars}
          onChange={(checked) => handleLocalChange('require_special_chars', checked)}
          disabled={updatePolicy.isPending}
        />

        {/* Password Expiry */}
        <div className="flex items-center justify-between py-3 border-t border-stone-100 dark:border-stone-800">
          <div>
            <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
              {t('settings.security.passwordExpiry', 'Password Expiry')}
            </p>
            <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
              {t('settings.security.passwordExpiryDesc', '0 = never expires')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={0}
              max={365}
              value={displayPolicy.password_expiry_days}
              onChange={(e) => handleLocalChange('password_expiry_days', parseInt(e.target.value, 10))}
              className="w-20 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
            />
            <span className="text-sm text-stone-500">{t('common.days', 'days')}</span>
          </div>
        </div>
      </SettingCard>

      {/* Account Lockout */}
      <SettingCard
        title={t('settings.security.accountLockout', 'Account Lockout')}
        description={t('settings.security.accountLockoutDesc', 'Protection against brute force attacks')}
      >
        <SettingRow
          title={t('settings.security.enableLockout', 'Enable Account Lockout')}
          description={t('settings.security.enableLockoutDesc', 'Lock accounts after failed login attempts')}
          checked={policy?.enable_account_lockout ?? true}
          onChange={(checked) => handleToggle('enable_account_lockout', checked)}
          disabled={updatePolicy.isPending}
        />

        {policy?.enable_account_lockout && (
          <>
            <div className="flex items-center justify-between py-3">
              <div>
                <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                  {t('settings.security.maxAttempts', 'Max Failed Attempts')}
                </p>
              </div>
              <input
                type="number"
                min={3}
                max={10}
                value={displayPolicy.max_failed_attempts}
                onChange={(e) => handleLocalChange('max_failed_attempts', parseInt(e.target.value, 10))}
                className="w-20 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
              />
            </div>

            <div className="flex items-center justify-between py-3 border-t border-stone-100 dark:border-stone-800">
              <div>
                <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                  {t('settings.security.lockoutDuration', 'Lockout Duration')}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={5}
                  max={1440}
                  value={displayPolicy.lockout_duration_minutes}
                  onChange={(e) => handleLocalChange('lockout_duration_minutes', parseInt(e.target.value, 10))}
                  className="w-20 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                />
                <span className="text-sm text-stone-500">{t('common.minutes', 'minutes')}</span>
              </div>
            </div>
          </>
        )}

        {hasChanges && (
          <div className="py-3 border-t border-stone-100 dark:border-stone-800">
            <button
              onClick={handleSavePasswordPolicy}
              disabled={updatePolicy.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {updatePolicy.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                t('common.saveChanges', 'Save Changes')
              )}
            </button>
          </div>
        )}
      </SettingCard>

      {/* IP Access Control */}
      <SettingCard
        title={t('settings.security.ipAccess', 'IP Access Control')}
        description={t('settings.security.ipAccessDesc', 'Restrict access by IP address')}
      >
        <SettingRow
          title={t('settings.security.enableIPRestriction', 'Enable IP Restriction')}
          description={t('settings.security.enableIPRestrictionDesc', 'Only allow access from specified IPs')}
          checked={policy?.ip_restriction_enabled ?? false}
          onChange={(checked) => handleToggle('ip_restriction_enabled', checked)}
          disabled={updatePolicy.isPending}
        />

        {policy?.ip_restriction_enabled && (
          <>
            {/* IP Allowlist */}
            <div className="py-3 border-t border-stone-100 dark:border-stone-800">
              <div className="flex items-center gap-3 mb-3">
                <Globe className="h-5 w-5 text-stone-400" />
                <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                  {t('settings.security.ipAllowlist', 'IP Allowlist')}
                </p>
              </div>
              <div className="flex flex-wrap gap-2 mb-3">
                {(policy?.ip_allowlist || []).map((ip) => (
                  <div
                    key={ip}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 rounded-full text-sm"
                  >
                    {ip}
                    <button
                      onClick={() => handleRemoveIP('allowed', ip)}
                      className="ml-1 hover:text-green-900 dark:hover:text-green-300"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newAllowedIP}
                  onChange={(e) => setNewAllowedIP(e.target.value)}
                  placeholder={t('settings.security.ipPlaceholder', '192.168.1.0/24')}
                  className="flex-1 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                />
                <button
                  onClick={() => handleAddIP('allowed')}
                  disabled={updatePolicy.isPending || !newAllowedIP.trim()}
                  className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-teal-600 hover:text-teal-700 border border-teal-600 hover:border-teal-700 rounded-lg transition-colors disabled:opacity-50"
                >
                  <Plus className="h-4 w-4" />
                  {t('common.add', 'Add')}
                </button>
              </div>
            </div>

            {/* IP Blocklist */}
            <div className="py-3 border-t border-stone-100 dark:border-stone-800">
              <div className="flex items-center gap-3 mb-3">
                <Shield className="h-5 w-5 text-stone-400" />
                <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                  {t('settings.security.ipBlocklist', 'IP Blocklist')}
                </p>
              </div>
              <div className="flex flex-wrap gap-2 mb-3">
                {(policy?.ip_blocklist || []).map((ip) => (
                  <div
                    key={ip}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-full text-sm"
                  >
                    {ip}
                    <button
                      onClick={() => handleRemoveIP('blocked', ip)}
                      className="ml-1 hover:text-red-900 dark:hover:text-red-300"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newBlockedIP}
                  onChange={(e) => setNewBlockedIP(e.target.value)}
                  placeholder={t('settings.security.ipPlaceholder', '10.0.0.0/8')}
                  className="flex-1 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                />
                <button
                  onClick={() => handleAddIP('blocked')}
                  disabled={updatePolicy.isPending || !newBlockedIP.trim()}
                  className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-red-600 hover:text-red-700 border border-red-600 hover:border-red-700 rounded-lg transition-colors disabled:opacity-50"
                >
                  <Plus className="h-4 w-4" />
                  {t('common.add', 'Add')}
                </button>
              </div>
            </div>
          </>
        )}
      </SettingCard>

      {/* Egress Control */}
      <SettingCard
        title={t('settings.security.egressControl', 'Egress Control')}
        description={t('settings.security.egressControlDesc', 'Control outbound network access')}
      >
        <div className="flex items-start gap-3 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg mb-4">
          <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-amber-800 dark:text-amber-200">
            {t(
              'settings.security.egressWarning',
              'Egress control helps prevent data exfiltration. Only allow domains that are necessary for your integrations.'
            )}
          </p>
        </div>

        <SettingRow
          title={t('settings.security.enableEgressControl', 'Enable Egress Control')}
          description={t('settings.security.enableEgressControlDesc', 'Restrict outbound connections to allowed domains')}
          checked={policy?.egress_control_enabled ?? false}
          onChange={(checked) => handleToggle('egress_control_enabled', checked)}
          disabled={updatePolicy.isPending}
        />

        {policy?.egress_control_enabled && (
          <div className="py-3 border-t border-stone-100 dark:border-stone-800">
            <p className="text-sm font-medium text-stone-900 dark:text-stone-100 mb-3">
              {t('settings.security.allowedDomains', 'Allowed Domains')}
            </p>
            <div className="flex flex-wrap gap-2 mb-3">
              {(policy?.egress_allowed_domains || []).map((domain) => (
                <div
                  key={domain}
                  className="inline-flex items-center gap-1 px-3 py-1 bg-stone-100 dark:bg-stone-800 text-stone-700 dark:text-stone-300 rounded-full text-sm"
                >
                  {domain}
                  <button
                    onClick={() => handleRemoveEgressDomain(domain)}
                    className="ml-1 hover:text-stone-900 dark:hover:text-stone-100"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newEgressDomain}
                onChange={(e) => setNewEgressDomain(e.target.value)}
                placeholder={t('settings.security.domainPlaceholder', 'api.example.com')}
                className="flex-1 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
              />
              <button
                onClick={handleAddEgressDomain}
                disabled={updatePolicy.isPending || !newEgressDomain.trim()}
                className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-teal-600 hover:text-teal-700 border border-teal-600 hover:border-teal-700 rounded-lg transition-colors disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                {t('common.add', 'Add')}
              </button>
            </div>
          </div>
        )}
      </SettingCard>

      {/* Audit Logs */}
      <SettingCard
        title={t('settings.security.auditLogs', 'Audit Logs')}
        description={t('settings.security.auditLogsDesc', 'Track security-related events')}
        action={
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetchAudit()}
              disabled={isLoadingAudit}
              className="p-2 text-stone-500 hover:text-stone-700 dark:hover:text-stone-300"
              title={t('common.refresh', 'Refresh')}
            >
              <RefreshCw className={`h-4 w-4 ${isLoadingAudit ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={handleExportAuditLogs}
              disabled={!auditData?.logs?.length}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-teal-600 hover:text-teal-700 border border-teal-600 hover:border-teal-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <Download className="h-4 w-4" />
              {t('settings.security.exportLogs', 'Export')}
            </button>
          </div>
        }
      >
        <div className="py-2">
          {isLoadingAudit ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-teal-600" />
            </div>
          ) : !auditData?.logs?.length ? (
            <div className="text-center py-8 text-stone-500">
              <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>{t('settings.security.noLogs', 'No audit logs available')}</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {auditData.logs.map((log: AuditLog) => (
                <div
                  key={log.id}
                  className="flex items-start gap-3 p-3 bg-stone-50 dark:bg-stone-800 rounded-lg text-sm"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-stone-900 dark:text-stone-100">
                        {log.action}
                      </span>
                      <span className="text-stone-500">•</span>
                      <span className="text-stone-500">{log.resource_type}</span>
                    </div>
                    <div className="text-stone-500 mt-1">
                      {log.actor_email || log.actor_id}
                      {log.ip_address && ` • ${log.ip_address}`}
                    </div>
                  </div>
                  <span className="text-stone-400 text-xs whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </SettingCard>
    </div>
  );
}

export default SecuritySettingsPage;
