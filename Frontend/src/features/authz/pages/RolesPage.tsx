/**
 * Roles Management Page
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  Key,
  Plus,
  Edit,
  Trash2,
  ChevronDown,
  ChevronRight,
  Shield,
  Check,
  X,
  Copy,
} from 'lucide-react';
import { authzClient } from '../api/authzClient';
import { RequirePermission } from '../components/PermissionGate';
import type { Role, PermissionGroup, RolePermissionAssignment } from '../api/authzTypes';

export function RolesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const { data: roles, isLoading: rolesLoading } = useQuery({
    queryKey: ['roles', { includePermissions: true }],
    queryFn: () => authzClient.listRoles(true),
  });

  const { data: permissionGroups } = useQuery({
    queryKey: ['permissions', 'grouped'],
    queryFn: () => authzClient.listPermissionsGrouped(),
  });

  const deleteMutation = useMutation({
    mutationFn: (roleId: string) => authzClient.deleteRole(roleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      setSelectedRole(null);
    },
  });

  if (rolesLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600" />
      </div>
    );
  }

  return (
    <div className="flex gap-6 h-full">
      {/* Role List */}
      <div className="w-80 flex-shrink-0 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-medium text-stone-900 dark:text-stone-100">
            {t('authz.roles.title', 'Roles')}
          </h2>
          <RequirePermission permission="security.role.create">
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors"
            >
              <Plus className="h-4 w-4" />
              {t('authz.roles.create', 'Create')}
            </button>
          </RequirePermission>
        </div>

        <div className="space-y-2">
          {roles?.items.map((role) => (
            <button
              key={role.id}
              onClick={() => setSelectedRole(role)}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${
                selectedRole?.id === role.id
                  ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/20'
                  : 'border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-800 hover:border-stone-300 dark:hover:border-stone-600'
              }`}
            >
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
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
                {role.name}
              </p>
              <p className="text-xs text-stone-400 dark:text-stone-500 mt-1">
                {role.permissions.length} {t('authz.permissions', 'permissions')}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Role Detail */}
      <div className="flex-1 min-w-0">
        {selectedRole ? (
          <RoleDetail
            role={selectedRole}
            permissionGroups={permissionGroups || []}
            onDelete={() => deleteMutation.mutate(selectedRole.id)}
            isDeleting={deleteMutation.isPending}
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-stone-500 dark:text-stone-400">
            <Key className="h-12 w-12 mb-4" />
            <p>{t('authz.roles.selectRole', 'Select a role to view details')}</p>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateRoleModal
          onClose={() => setShowCreateModal(false)}
          permissionGroups={permissionGroups || []}
        />
      )}
    </div>
  );
}

interface RoleDetailProps {
  role: Role;
  permissionGroups: PermissionGroup[];
  onDelete: () => void;
  isDeleting: boolean;
}

function RoleDetail({ role, permissionGroups, onDelete, isDeleting }: RoleDetailProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());
  const [pendingChanges, setPendingChanges] = useState<Map<string, 'allow' | 'deny' | null>>(
    new Map()
  );

  // Get current permission state (role + pending changes)
  const rolePermissions = new Map(role.permissions.map((p) => [p.permission_key, p.effect]));

  const getPermissionState = (key: string): 'allow' | 'deny' | null => {
    if (pendingChanges.has(key)) {
      return pendingChanges.get(key) || null;
    }
    return rolePermissions.get(key) || null;
  };

  const togglePermission = (key: string) => {
    const current = getPermissionState(key);
    let next: 'allow' | 'deny' | null;
    if (current === null) next = 'allow';
    else if (current === 'allow') next = null;
    else next = null; // deny -> remove

    setPendingChanges((prev) => {
      const next_map = new Map(prev);
      if (next === rolePermissions.get(key)) {
        next_map.delete(key);
      } else {
        next_map.set(key, next);
      }
      return next_map;
    });
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const add: RolePermissionAssignment[] = [];
      const remove: string[] = [];

      for (const [key, effect] of pendingChanges) {
        if (effect === null) {
          remove.push(key);
        } else {
          add.push({ permission_key: key, effect });
        }
      }

      return authzClient.updateRolePermissions(role.id, { add, remove });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      setPendingChanges(new Map());
    },
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

  const hasChanges = pendingChanges.size > 0;

  return (
    <div className="bg-white dark:bg-stone-800 rounded-lg border border-stone-200 dark:border-stone-700 h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-stone-200 dark:border-stone-700">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-medium text-stone-900 dark:text-stone-100">
                {role.title || role.name}
              </h2>
              {role.is_system && (
                <span className="px-2 py-0.5 text-xs bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 rounded">
                  {t('authz.roles.system', 'System')}
                </span>
              )}
            </div>
            <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
              {role.name}
            </p>
            {role.description && (
              <p className="text-sm text-stone-600 dark:text-stone-400 mt-2">
                {role.description}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            {!role.is_system && (
              <RequirePermission permission="security.role.delete">
                <button
                  onClick={onDelete}
                  disabled={isDeleting}
                  className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                >
                  <Trash2 className="h-5 w-5" />
                </button>
              </RequirePermission>
            )}
          </div>
        </div>
      </div>

      {/* Permissions */}
      <div className="flex-1 overflow-auto p-4">
        <div className="space-y-2">
          {permissionGroups.map((group) => (
            <div
              key={group.module_key}
              className="border border-stone-200 dark:border-stone-700 rounded-lg overflow-hidden"
            >
              <button
                onClick={() => toggleModule(group.module_key)}
                className="w-full px-4 py-2 flex items-center justify-between hover:bg-stone-50 dark:hover:bg-stone-700/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  {expandedModules.has(group.module_key) ? (
                    <ChevronDown className="h-4 w-4 text-stone-400" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-stone-400" />
                  )}
                  <span className="font-medium text-stone-900 dark:text-stone-100">
                    {group.module_title}
                  </span>
                </div>
              </button>

              {expandedModules.has(group.module_key) && (
                <div className="border-t border-stone-200 dark:border-stone-700">
                  {Object.entries(group.features).map(([feature, permissions]) => (
                    <div key={feature}>
                      <div className="px-4 py-1.5 bg-stone-50 dark:bg-stone-800/50 text-sm text-stone-600 dark:text-stone-400">
                        {feature}
                      </div>
                      {permissions.map((perm) => {
                        const state = getPermissionState(perm.key);
                        return (
                          <div
                            key={perm.key}
                            className="px-4 py-2 flex items-center justify-between hover:bg-stone-50 dark:hover:bg-stone-700/30"
                          >
                            <div>
                              <p className="text-sm text-stone-900 dark:text-stone-100">
                                {perm.title}
                              </p>
                              <code className="text-xs text-stone-500 dark:text-stone-400">
                                {perm.key}
                              </code>
                            </div>
                            <RequirePermission permission="security.role.update">
                              <button
                                onClick={() => togglePermission(perm.key)}
                                className={`p-1 rounded transition-colors ${
                                  state === 'allow'
                                    ? 'text-green-600 bg-green-50 dark:bg-green-900/30'
                                    : state === 'deny'
                                    ? 'text-red-600 bg-red-50 dark:bg-red-900/30'
                                    : 'text-stone-400 hover:text-stone-600'
                                }`}
                              >
                                {state === 'allow' ? (
                                  <Check className="h-5 w-5" />
                                ) : state === 'deny' ? (
                                  <X className="h-5 w-5" />
                                ) : (
                                  <div className="h-5 w-5 border-2 border-current rounded" />
                                )}
                              </button>
                            </RequirePermission>
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Save Bar */}
      {hasChanges && (
        <div className="p-4 border-t border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-900/50">
          <div className="flex items-center justify-between">
            <span className="text-sm text-stone-600 dark:text-stone-400">
              {pendingChanges.size} {t('authz.roles.pendingChanges', 'pending changes')}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPendingChanges(new Map())}
                className="px-4 py-2 text-sm text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg transition-colors"
              >
                {t('common.cancel', 'Cancel')}
              </button>
              <button
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
                className="px-4 py-2 text-sm bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-50 transition-colors"
              >
                {saveMutation.isPending ? t('common.saving', 'Saving...') : t('common.save', 'Save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface CreateRoleModalProps {
  onClose: () => void;
  permissionGroups: PermissionGroup[];
}

function CreateRoleModal({ onClose, permissionGroups }: CreateRoleModalProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  const createMutation = useMutation({
    mutationFn: () =>
      authzClient.createRole({
        name,
        title: title || undefined,
        description: description || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-stone-800 rounded-lg w-full max-w-md p-6">
        <h2 className="text-lg font-medium text-stone-900 dark:text-stone-100 mb-4">
          {t('authz.roles.createTitle', 'Create Role')}
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
              {t('authz.roles.name', 'Name')} *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my_role"
              className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
              {t('authz.roles.displayTitle', 'Display Title')}
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="My Role"
              className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
              {t('authz.roles.description', 'Description')}
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-700 rounded-lg transition-colors"
          >
            {t('common.cancel', 'Cancel')}
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!name || createMutation.isPending}
            className="px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-50 transition-colors"
          >
            {createMutation.isPending ? t('common.creating', 'Creating...') : t('common.create', 'Create')}
          </button>
        </div>
      </div>
    </div>
  );
}

export default RolesPage;
