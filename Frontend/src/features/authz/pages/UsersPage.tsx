/**
 * Users Management Page - Role Assignment
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Users, Search, Key, Check, X, ChevronDown } from 'lucide-react';
import { authzClient } from '../api/authzClient';
import type { UserWithRoles, RoleSummary, Role } from '../api/authzTypes';

export function UsersPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [selectedUser, setSelectedUser] = useState<UserWithRoles | null>(null);
  const limit = 20;

  const { data: usersData, isLoading: usersLoading } = useQuery({
    queryKey: ['authz-users', { search, limit, offset: page * limit }],
    queryFn: () =>
      authzClient.listUsersWithRoles({
        search: search || undefined,
        limit,
        offset: page * limit,
      }),
  });

  const { data: rolesData } = useQuery({
    queryKey: ['roles'],
    queryFn: () => authzClient.listRoles(false),
  });

  if (usersLoading) {
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
          {t('authz.users.title', 'User Role Assignment')}
        </h2>
        <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
          {t('authz.users.description', 'Manage role assignments for users')}
        </p>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-stone-400" />
        <input
          type="text"
          placeholder={t('authz.users.search', 'Search users by email or name...')}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          className="w-full pl-10 pr-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
      </div>

      {/* User List */}
      <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-800/50">
              <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                {t('authz.users.user', 'User')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                {t('authz.users.roles', 'Roles')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                {t('authz.users.created', 'Created')}
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                {t('authz.users.actions', 'Actions')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-200 dark:divide-stone-700">
            {usersData?.items.map((user) => (
              <tr
                key={user.id}
                className="hover:bg-stone-50 dark:hover:bg-stone-700/30 transition-colors"
              >
                <td className="px-4 py-4">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-teal-100 dark:bg-teal-900/50 flex items-center justify-center text-teal-600 dark:text-teal-400 font-medium">
                      {user.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium text-stone-900 dark:text-stone-100">
                        {user.name}
                      </p>
                      <p className="text-sm text-stone-500 dark:text-stone-400">
                        {user.email}
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-4">
                  <div className="flex flex-wrap gap-1">
                    {user.roles.length > 0 ? (
                      user.roles.map((role) => (
                        <span
                          key={role.id}
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                            role.is_system
                              ? 'bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300'
                              : 'bg-teal-100 dark:bg-teal-900/50 text-teal-700 dark:text-teal-300'
                          }`}
                        >
                          <Key className="h-3 w-3 mr-1" />
                          {role.title || role.name}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-stone-400 dark:text-stone-500">
                        {t('authz.users.noRoles', 'No roles assigned')}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-4 text-sm text-stone-500 dark:text-stone-400">
                  {new Date(user.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-4 text-right">
                  <button
                    onClick={() => setSelectedUser(user)}
                    className="px-3 py-1.5 text-sm text-teal-600 dark:text-teal-400 hover:bg-teal-50 dark:hover:bg-teal-900/20 rounded-lg transition-colors"
                  >
                    {t('authz.users.editRoles', 'Edit Roles')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {usersData?.items.length === 0 && (
          <div className="py-12 text-center text-stone-500 dark:text-stone-400">
            {t('authz.users.noUsers', 'No users found')}
          </div>
        )}
      </div>

      {/* Pagination */}
      {usersData && usersData.total > limit && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-stone-500 dark:text-stone-400">
            {t('authz.users.showing', 'Showing {{from}}-{{to}} of {{total}}', {
              from: page * limit + 1,
              to: Math.min((page + 1) * limit, usersData.total),
              total: usersData.total,
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
              disabled={(page + 1) * limit >= usersData.total}
              className="px-3 py-1.5 text-sm border border-stone-300 dark:border-stone-600 rounded-lg disabled:opacity-50 hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors"
            >
              {t('common.next', 'Next')}
            </button>
          </div>
        </div>
      )}

      {/* Edit Roles Modal */}
      {selectedUser && rolesData && (
        <EditRolesModal
          user={selectedUser}
          allRoles={rolesData.items}
          onClose={() => setSelectedUser(null)}
        />
      )}
    </div>
  );
}

interface EditRolesModalProps {
  user: UserWithRoles;
  allRoles: Role[];
  onClose: () => void;
}

function EditRolesModal({ user, allRoles, onClose }: EditRolesModalProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedRoleIds, setSelectedRoleIds] = useState<Set<string>>(
    new Set(user.roles.map((r) => r.id))
  );

  const toggleRole = (roleId: string) => {
    setSelectedRoleIds((prev) => {
      const next = new Set(prev);
      if (next.has(roleId)) {
        next.delete(roleId);
      } else {
        next.add(roleId);
      }
      return next;
    });
  };

  const saveMutation = useMutation({
    mutationFn: () =>
      authzClient.assignRolesToUser(user.id, Array.from(selectedRoleIds)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['authz-users'] });
      onClose();
    },
  });

  const hasChanges =
    selectedRoleIds.size !== user.roles.length ||
    user.roles.some((r) => !selectedRoleIds.has(r.id));

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-stone-800 rounded-lg w-full max-w-md p-6 max-h-[80vh] flex flex-col">
        <div className="mb-4">
          <h2 className="text-lg font-medium text-stone-900 dark:text-stone-100">
            {t('authz.users.editRolesTitle', 'Edit Roles')}
          </h2>
          <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
            {user.name} ({user.email})
          </p>
        </div>

        <div className="flex-1 overflow-auto space-y-2">
          {allRoles.map((role) => (
            <button
              key={role.id}
              onClick={() => toggleRole(role.id)}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${
                selectedRoleIds.has(role.id)
                  ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/20'
                  : 'border-stone-200 dark:border-stone-700 hover:border-stone-300 dark:hover:border-stone-600'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Key className="h-4 w-4 text-teal-500" />
                  <span className="font-medium text-stone-900 dark:text-stone-100">
                    {role.title || role.name}
                  </span>
                  {role.is_system && (
                    <span className="px-1.5 py-0.5 text-xs bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 rounded">
                      {t('authz.roles.system', 'System')}
                    </span>
                  )}
                </div>
                {selectedRoleIds.has(role.id) && (
                  <Check className="h-5 w-5 text-teal-600" />
                )}
              </div>
              {role.description && (
                <p className="text-sm text-stone-500 dark:text-stone-400 mt-1 ml-6">
                  {role.description}
                </p>
              )}
            </button>
          ))}
        </div>

        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-stone-200 dark:border-stone-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-700 rounded-lg transition-colors"
          >
            {t('common.cancel', 'Cancel')}
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!hasChanges || saveMutation.isPending}
            className="px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-50 transition-colors"
          >
            {saveMutation.isPending ? t('common.saving', 'Saving...') : t('common.save', 'Save')}
          </button>
        </div>
      </div>
    </div>
  );
}

export default UsersPage;
