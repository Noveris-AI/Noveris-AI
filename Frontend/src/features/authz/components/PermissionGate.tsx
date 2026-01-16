/**
 * Permission-based UI gating components
 */

import React from 'react';
import { useAuthz, usePermission, useModuleEnabled, useAnyPermission } from '../hooks/AuthzContext';

interface RequirePermissionProps {
  permission: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  /**
   * If true, shows disabled state instead of hiding
   */
  showDisabled?: boolean;
}

/**
 * Component that only renders children if user has the specified permission.
 *
 * @example
 * <RequirePermission permission="node.node.create">
 *   <Button>Create Node</Button>
 * </RequirePermission>
 *
 * @example
 * <RequirePermission permission="node.node.create" showDisabled>
 *   <Button disabled={!hasPermission}>Create Node</Button>
 * </RequirePermission>
 */
export function RequirePermission({
  permission,
  children,
  fallback = null,
  showDisabled = false,
}: RequirePermissionProps) {
  const hasPermission = usePermission(permission);
  const { isLoading } = useAuthz();

  if (isLoading) {
    return null;
  }

  if (!hasPermission) {
    if (showDisabled) {
      // Clone children and add disabled prop
      return (
        <>
          {React.Children.map(children, (child) => {
            if (React.isValidElement(child)) {
              return React.cloneElement(child as React.ReactElement<{ disabled?: boolean }>, {
                disabled: true,
              });
            }
            return child;
          })}
        </>
      );
    }
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

interface RequireAnyPermissionProps {
  permissions: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * Component that renders children if user has any of the specified permissions.
 */
export function RequireAnyPermission({
  permissions,
  children,
  fallback = null,
}: RequireAnyPermissionProps) {
  const hasAny = useAnyPermission(permissions);
  const { isLoading } = useAuthz();

  if (isLoading) {
    return null;
  }

  if (!hasAny) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

interface RequireModuleProps {
  module: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * Component that only renders children if the specified module is enabled.
 *
 * @example
 * <RequireModule module="deploy">
 *   <DeploymentSection />
 * </RequireModule>
 */
export function RequireModule({
  module,
  children,
  fallback = null,
}: RequireModuleProps) {
  const isEnabled = useModuleEnabled(module);
  const { isLoading } = useAuthz();

  if (isLoading) {
    return null;
  }

  if (!isEnabled) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

interface RequireSuperAdminProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * Component that only renders children if user is super admin.
 */
export function RequireSuperAdmin({
  children,
  fallback = null,
}: RequireSuperAdminProps) {
  const { isSuperAdmin, isLoading } = useAuthz();

  if (isLoading) {
    return null;
  }

  if (!isSuperAdmin) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

interface PermissionGateProps {
  permission?: string;
  permissions?: string[];
  module?: string;
  requireSuperAdmin?: boolean;
  requireAll?: boolean;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * Flexible permission gate component that supports multiple check types.
 *
 * @example
 * // Single permission
 * <PermissionGate permission="node.node.view">...</PermissionGate>
 *
 * // Multiple permissions (any)
 * <PermissionGate permissions={["node.node.view", "node.node.create"]}>...</PermissionGate>
 *
 * // Multiple permissions (all)
 * <PermissionGate permissions={["node.node.view", "node.node.create"]} requireAll>...</PermissionGate>
 *
 * // Module + permission
 * <PermissionGate module="deploy" permission="deploy.deployment.view">...</PermissionGate>
 */
export function PermissionGate({
  permission,
  permissions,
  module,
  requireSuperAdmin = false,
  requireAll = false,
  children,
  fallback = null,
}: PermissionGateProps) {
  const {
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    isModuleEnabled,
    isSuperAdmin,
    isLoading,
  } = useAuthz();

  if (isLoading) {
    return null;
  }

  // Check super admin if required
  if (requireSuperAdmin && !isSuperAdmin) {
    return <>{fallback}</>;
  }

  // Check module if specified
  if (module && !isModuleEnabled(module)) {
    return <>{fallback}</>;
  }

  // Check single permission
  if (permission && !hasPermission(permission)) {
    return <>{fallback}</>;
  }

  // Check multiple permissions
  if (permissions && permissions.length > 0) {
    const hasPerms = requireAll
      ? hasAllPermissions(permissions)
      : hasAnyPermission(permissions);
    if (!hasPerms) {
      return <>{fallback}</>;
    }
  }

  return <>{children}</>;
}

export default RequirePermission;
