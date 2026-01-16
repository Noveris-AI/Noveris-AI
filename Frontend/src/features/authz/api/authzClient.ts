/**
 * Authorization API client
 *
 * Handles all authorization-related API calls.
 * Uses shared API configuration for consistent base URL handling.
 */

import { API_CONFIG } from '@shared/config/api'
import type {
  AuthzMeResponse,
  ModuleListResponse,
  Module,
  PermissionListResponse,
  PermissionGroup,
  RoleListResponse,
  Role,
  RoleCreate,
  RoleUpdate,
  RolePermissionsBulkUpdate,
  UserListResponse,
  UserRoleAssign,
  RoleSummary,
  TenantModuleSetting,
  TenantModuleSettingsBulkUpdate,
  AuditLogListResponse,
} from './authzTypes';

class AuthzClient {
  private readonly baseUrl: string

  constructor() {
    this.baseUrl = `${API_CONFIG.BASE_URL}${API_CONFIG.API_VERSION}`
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      credentials: 'include',
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail?.message || error.detail || `Request failed: ${response.status}`);
    }

    return response.json();
  }

  // ========================================================================
  // Current User Authorization
  // ========================================================================

  async getMe(): Promise<AuthzMeResponse> {
    return this.request<AuthzMeResponse>('/authz/me');
  }

  // ========================================================================
  // Module Management
  // ========================================================================

  async listModules(): Promise<ModuleListResponse> {
    return this.request<ModuleListResponse>('/authz/modules');
  }

  async getModule(moduleKey: string): Promise<Module> {
    return this.request<Module>(`/authz/modules/${moduleKey}`);
  }

  async updateModule(moduleKey: string, data: Partial<Module>): Promise<Module> {
    return this.request<Module>(`/authz/modules/${moduleKey}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // ========================================================================
  // Tenant Module Settings
  // ========================================================================

  async getTenantModuleSettings(): Promise<TenantModuleSetting[]> {
    return this.request<TenantModuleSetting[]>('/authz/tenant-modules');
  }

  async updateTenantModuleSetting(
    moduleKey: string,
    enabled: boolean
  ): Promise<TenantModuleSetting> {
    return this.request<TenantModuleSetting>(`/authz/tenant-modules/${moduleKey}`, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    });
  }

  async bulkUpdateTenantModuleSettings(
    settings: Record<string, boolean>
  ): Promise<TenantModuleSetting[]> {
    return this.request<TenantModuleSetting[]>('/authz/tenant-modules/bulk', {
      method: 'POST',
      body: JSON.stringify({ settings } as TenantModuleSettingsBulkUpdate),
    });
  }

  // ========================================================================
  // Permission Management
  // ========================================================================

  async listPermissions(moduleKey?: string): Promise<PermissionListResponse> {
    const params = moduleKey ? `?module_key=${moduleKey}` : '';
    return this.request<PermissionListResponse>(`/authz/permissions${params}`);
  }

  async listPermissionsGrouped(): Promise<PermissionGroup[]> {
    return this.request<PermissionGroup[]>('/authz/permissions/grouped');
  }

  // ========================================================================
  // Role Management
  // ========================================================================

  async listRoles(includePermissions = false): Promise<RoleListResponse> {
    const params = includePermissions ? '?include_permissions=true' : '';
    return this.request<RoleListResponse>(`/authz/roles${params}`);
  }

  async getRole(roleId: string): Promise<Role> {
    return this.request<Role>(`/authz/roles/${roleId}`);
  }

  async createRole(data: RoleCreate): Promise<Role> {
    return this.request<Role>('/authz/roles', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateRole(roleId: string, data: RoleUpdate): Promise<Role> {
    return this.request<Role>(`/authz/roles/${roleId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteRole(roleId: string): Promise<void> {
    await fetch(`${this.baseUrl}/authz/roles/${roleId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
  }

  async updateRolePermissions(
    roleId: string,
    data: RolePermissionsBulkUpdate
  ): Promise<Role> {
    return this.request<Role>(`/authz/roles/${roleId}/permissions`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ========================================================================
  // User Role Management
  // ========================================================================

  async listUsersWithRoles(params?: {
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<UserListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.set('search', params.search);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());

    const queryString = searchParams.toString();
    return this.request<UserListResponse>(
      `/authz/users${queryString ? `?${queryString}` : ''}`
    );
  }

  async getUserRoles(userId: string): Promise<{ user_id: string; roles: RoleSummary[] }> {
    return this.request<{ user_id: string; roles: RoleSummary[] }>(
      `/authz/users/${userId}/roles`
    );
  }

  async assignRolesToUser(userId: string, roleIds: string[]): Promise<{ user_id: string; roles: RoleSummary[] }> {
    return this.request<{ user_id: string; roles: RoleSummary[] }>(
      `/authz/users/${userId}/roles`,
      {
        method: 'POST',
        body: JSON.stringify({ role_ids: roleIds } as UserRoleAssign),
      }
    );
  }

  // ========================================================================
  // Audit Logs
  // ========================================================================

  async listAuditLogs(params?: {
    action?: string;
    resource_type?: string;
    actor_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<AuditLogListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.action) searchParams.set('action', params.action);
    if (params?.resource_type) searchParams.set('resource_type', params.resource_type);
    if (params?.actor_id) searchParams.set('actor_id', params.actor_id);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());

    const queryString = searchParams.toString();
    return this.request<AuditLogListResponse>(
      `/authz/audit-logs${queryString ? `?${queryString}` : ''}`
    );
  }

  // ========================================================================
  // Import/Export
  // ========================================================================

  async exportConfig(): Promise<unknown> {
    return this.request<unknown>('/authz/export');
  }

  async importConfig(data: unknown): Promise<{ success: boolean; results: unknown }> {
    return this.request<{ success: boolean; results: unknown }>('/authz/import', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ========================================================================
  // Manifest Sync
  // ========================================================================

  async syncManifest(): Promise<{ success: boolean; stats: unknown }> {
    return this.request<{ success: boolean; stats: unknown }>('/authz/sync-manifest', {
      method: 'POST',
    });
  }
}

export const authzClient = new AuthzClient();
export default authzClient;
