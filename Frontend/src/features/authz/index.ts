/**
 * Authorization feature exports
 */

// API
export { authzClient } from './api/authzClient';
export type * from './api/authzTypes';

// Context & Hooks
export {
  AuthzProvider,
  useAuthz,
  usePermission,
  useAnyPermission,
  useAllPermissions,
  useModuleEnabled,
  useSuperAdmin,
} from './hooks/AuthzContext';

// Components
export {
  RequirePermission,
  RequireAnyPermission,
  RequireModule,
  RequireSuperAdmin,
  PermissionGate,
} from './components/PermissionGate';

// Pages
export { AuthzLayout } from './pages/AuthzLayout';
export { PermissionsPage } from './pages/PermissionsPage';
export { ModulesPage } from './pages/ModulesPage';
export { RolesPage } from './pages/RolesPage';
export { UsersPage } from './pages/UsersPage';
export { AuditLogsPage } from './pages/AuditLogsPage';
