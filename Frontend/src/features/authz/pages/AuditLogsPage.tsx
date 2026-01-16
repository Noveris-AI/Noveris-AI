/**
 * Audit Logs Page
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { History, Search, Filter, ChevronDown, ChevronUp } from 'lucide-react';
import { authzClient } from '../api/authzClient';
import type { AuditLog } from '../api/authzTypes';

const ACTION_COLORS: Record<string, string> = {
  'role.create': 'bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300',
  'role.update': 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300',
  'role.delete': 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300',
  'role.permissions.update': 'bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300',
  'user.roles.assign': 'bg-teal-100 text-teal-700 dark:bg-teal-900/50 dark:text-teal-300',
  'module.enable': 'bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300',
  'module.disable': 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300',
  'authz.import': 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300',
  'authz.sync_manifest': 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/50 dark:text-cyan-300',
};

export function AuditLogsPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(0);
  const [actionFilter, setActionFilter] = useState<string>('');
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string>('');
  const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set());
  const limit = 20;

  const { data: logsData, isLoading } = useQuery({
    queryKey: [
      'audit-logs',
      { action: actionFilter, resource_type: resourceTypeFilter, limit, offset: page * limit },
    ],
    queryFn: () =>
      authzClient.listAuditLogs({
        action: actionFilter || undefined,
        resource_type: resourceTypeFilter || undefined,
        limit,
        offset: page * limit,
      }),
  });

  const toggleExpand = (logId: string) => {
    setExpandedLogs((prev) => {
      const next = new Set(prev);
      if (next.has(logId)) {
        next.delete(logId);
      } else {
        next.add(logId);
      }
      return next;
    });
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
      {/* Header */}
      <div>
        <h2 className="text-lg font-medium text-stone-900 dark:text-stone-100">
          {t('authz.audit.title', 'Audit Logs')}
        </h2>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
          {t('authz.audit.description', 'View authorization change history')}
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="flex-1">
          <select
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPage(0);
            }}
            className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            <option value="">{t('authz.audit.allActions', 'All Actions')}</option>
            <option value="role.create">{t('authz.audit.action.role.create', 'Role Created')}</option>
            <option value="role.update">{t('authz.audit.action.role.update', 'Role Updated')}</option>
            <option value="role.delete">{t('authz.audit.action.role.delete', 'Role Deleted')}</option>
            <option value="role.permissions.update">
              {t('authz.audit.action.role.permissions', 'Permissions Updated')}
            </option>
            <option value="user.roles.assign">
              {t('authz.audit.action.user.roles', 'User Roles Assigned')}
            </option>
            <option value="module.enable">{t('authz.audit.action.module.enable', 'Module Enabled')}</option>
            <option value="module.disable">
              {t('authz.audit.action.module.disable', 'Module Disabled')}
            </option>
          </select>
        </div>
        <div className="flex-1">
          <select
            value={resourceTypeFilter}
            onChange={(e) => {
              setResourceTypeFilter(e.target.value);
              setPage(0);
            }}
            className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            <option value="">{t('authz.audit.allTypes', 'All Resource Types')}</option>
            <option value="role">{t('authz.audit.type.role', 'Role')}</option>
            <option value="user">{t('authz.audit.type.user', 'User')}</option>
            <option value="module">{t('authz.audit.type.module', 'Module')}</option>
            <option value="tenant_module">{t('authz.audit.type.tenant_module', 'Tenant Module')}</option>
            <option value="authz">{t('authz.audit.type.authz', 'Authorization')}</option>
          </select>
        </div>
      </div>

      {/* Logs List */}
      <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 divide-y divide-stone-200 dark:divide-stone-700">
        {logsData?.items.map((log) => (
          <AuditLogRow
            key={log.id}
            log={log}
            isExpanded={expandedLogs.has(log.id)}
            onToggle={() => toggleExpand(log.id)}
          />
        ))}

        {logsData?.items.length === 0 && (
          <div className="py-12 text-center text-stone-500 dark:text-stone-400">
            {t('authz.audit.noLogs', 'No audit logs found')}
          </div>
        )}
      </div>

      {/* Pagination */}
      {logsData && logsData.total > limit && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-stone-500 dark:text-stone-400">
            {t('authz.audit.showing', 'Showing {{from}}-{{to}} of {{total}}', {
              from: page * limit + 1,
              to: Math.min((page + 1) * limit, logsData.total),
              total: logsData.total,
            })}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg disabled:opacity-50 hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors"
            >
              {t('common.previous', 'Previous')}
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * limit >= logsData.total}
              className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg disabled:opacity-50 hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors"
            >
              {t('common.next', 'Next')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

interface AuditLogRowProps {
  log: AuditLog;
  isExpanded: boolean;
  onToggle: () => void;
}

function AuditLogRow({ log, isExpanded, onToggle }: AuditLogRowProps) {
  const { t } = useTranslation();
  const actionColor = ACTION_COLORS[log.action] || 'bg-stone-100 text-stone-700 dark:bg-stone-700 dark:text-stone-300';

  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-stone-50 dark:hover:bg-stone-700/30 transition-colors"
      >
        <div className="flex items-center gap-4">
          <History className="h-5 w-5 text-stone-400" />
          <div className="text-left">
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${actionColor}`}>
                {log.action}
              </span>
              <span className="text-sm text-stone-600 dark:text-stone-400">
                {log.resource_type}
                {log.resource_name && ` - ${log.resource_name}`}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-1 text-xs text-stone-500 dark:text-stone-400">
              <span>{log.actor_email || log.actor_id}</span>
              <span>·</span>
              <span>{new Date(log.created_at).toLocaleString()}</span>
              {log.ip_address && (
                <>
                  <span>·</span>
                  <span>{log.ip_address}</span>
                </>
              )}
            </div>
          </div>
        </div>
        {log.diff && (
          isExpanded ? (
            <ChevronUp className="h-5 w-5 text-stone-400" />
          ) : (
            <ChevronDown className="h-5 w-5 text-stone-400" />
          )
        )}
      </button>

      {isExpanded && log.diff && (
        <div className="px-4 pb-4">
          <div className="ml-9 p-3 bg-stone-50 dark:bg-stone-900/50 rounded-lg">
            <pre className="text-xs text-stone-600 dark:text-stone-400 overflow-auto">
              {JSON.stringify(log.diff, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default AuditLogsPage;
