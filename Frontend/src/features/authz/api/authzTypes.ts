/**
 * Authorization API types
 */

export interface AuthzMeResponse {
  user_id: string;
  tenant_id: string;
  email: string;
  name: string;
  enabled_modules: string[];
  permissions: string[];
  roles: RoleSummary[];
  is_super_admin: boolean;
}

export interface RoleSummary {
  id: string;
  name: string;
  title: string | null;
  is_system: boolean;
}

export interface Module {
  id: string;
  module_key: string;
  title: string;
  title_i18n: string | null;
  description: string | null;
  description_i18n: string | null;
  icon: string | null;
  order: number;
  default_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface Permission {
  id: string;
  key: string;
  module_key: string;
  feature: string;
  action: string;
  title: string;
  title_i18n: string | null;
  description: string | null;
  description_i18n: string | null;
  metadata: {
    ui?: { routes?: string[]; buttons?: string[] };
    api?: { resources?: { path: string; method: string }[] };
  } | null;
  created_at: string;
  updated_at: string;
}

export interface PermissionGroup {
  module_key: string;
  module_title: string;
  features: Record<string, Permission[]>;
}

export interface RolePermission {
  permission_key: string;
  effect: 'allow' | 'deny';
  priority: number;
}

export interface Role {
  id: string;
  tenant_id: string;
  name: string;
  title: string | null;
  title_i18n: string | null;
  description: string | null;
  description_i18n: string | null;
  is_system: boolean;
  parent_role_id: string | null;
  permissions: RolePermission[];
  created_at: string;
  updated_at: string;
}

export interface TenantModuleSetting {
  module_key: string;
  enabled: boolean;
  updated_at: string;
}

export interface UserWithRoles {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  roles: RoleSummary[];
  created_at: string;
}

export interface AuditLog {
  id: string;
  tenant_id: string;
  actor_id: string;
  actor_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  resource_name: string | null;
  diff: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

// Request types
export interface RoleCreate {
  name: string;
  title?: string;
  description?: string;
  parent_role_id?: string;
  permission_keys?: string[];
}

export interface RoleUpdate {
  name?: string;
  title?: string;
  description?: string;
  parent_role_id?: string;
}

export interface RolePermissionAssignment {
  permission_key: string;
  effect: 'allow' | 'deny';
  priority?: number;
}

export interface RolePermissionsBulkUpdate {
  add?: RolePermissionAssignment[];
  remove?: string[];
}

export interface UserRoleAssign {
  role_ids: string[];
}

export interface TenantModuleSettingsBulkUpdate {
  settings: Record<string, boolean>;
}

// Response types
export interface ListResponse<T> {
  items: T[];
  total: number;
}

export type ModuleListResponse = ListResponse<Module>;
export type PermissionListResponse = ListResponse<Permission>;
export type RoleListResponse = ListResponse<Role>;
export type UserListResponse = ListResponse<UserWithRoles>;
export type AuditLogListResponse = ListResponse<AuditLog>;
