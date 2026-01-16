/**
 * Authorization Context
 *
 * Provides authorization state and permission checking throughout the app.
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import { authzClient } from '../api/authzClient';
import type { AuthzMeResponse, RoleSummary } from '../api/authzTypes';

interface AuthzContextValue {
  // State
  isLoading: boolean;
  error: Error | null;
  isAuthenticated: boolean;

  // User info
  userId: string | null;
  tenantId: string | null;
  email: string | null;
  name: string | null;
  roles: RoleSummary[];
  isSuperAdmin: boolean;

  // Permissions
  enabledModules: Set<string>;
  permissions: Set<string>;

  // Methods
  hasPermission: (permissionKey: string) => boolean;
  hasAnyPermission: (permissionKeys: string[]) => boolean;
  hasAllPermissions: (permissionKeys: string[]) => boolean;
  isModuleEnabled: (moduleKey: string) => boolean;
  refresh: () => Promise<void>;
}

const AuthzContext = createContext<AuthzContextValue | null>(null);

interface AuthzProviderProps {
  children: React.ReactNode;
}

export function AuthzProvider({ children }: AuthzProviderProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [authzData, setAuthzData] = useState<AuthzMeResponse | null>(null);

  // Memoized sets for efficient lookups
  const enabledModules = useMemo(
    () => new Set(authzData?.enabled_modules || []),
    [authzData?.enabled_modules]
  );

  const permissions = useMemo(
    () => new Set(authzData?.permissions || []),
    [authzData?.permissions]
  );

  // Load authorization data
  const loadAuthz = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await authzClient.getMe();
      setAuthzData(data);
    } catch (err) {
      // Don't set error for 401 (not authenticated)
      if (err instanceof Error && !err.message.includes('401')) {
        setError(err);
      }
      setAuthzData(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load on mount
  useEffect(() => {
    loadAuthz();
  }, [loadAuthz]);

  // Permission checking methods
  const hasPermission = useCallback(
    (permissionKey: string): boolean => {
      if (!authzData) return false;
      if (authzData.is_super_admin) return true;

      // Check exact match
      if (permissions.has(permissionKey)) return true;

      // Check wildcard matches
      for (const perm of permissions) {
        if (matchPermission(perm, permissionKey)) return true;
      }

      return false;
    },
    [authzData, permissions]
  );

  const hasAnyPermission = useCallback(
    (permissionKeys: string[]): boolean => {
      return permissionKeys.some((key) => hasPermission(key));
    },
    [hasPermission]
  );

  const hasAllPermissions = useCallback(
    (permissionKeys: string[]): boolean => {
      return permissionKeys.every((key) => hasPermission(key));
    },
    [hasPermission]
  );

  const isModuleEnabled = useCallback(
    (moduleKey: string): boolean => {
      if (!authzData) return false;
      return enabledModules.has(moduleKey);
    },
    [authzData, enabledModules]
  );

  const value: AuthzContextValue = {
    isLoading,
    error,
    isAuthenticated: !!authzData,

    userId: authzData?.user_id || null,
    tenantId: authzData?.tenant_id || null,
    email: authzData?.email || null,
    name: authzData?.name || null,
    roles: authzData?.roles || [],
    isSuperAdmin: authzData?.is_super_admin || false,

    enabledModules,
    permissions,

    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    isModuleEnabled,
    refresh: loadAuthz,
  };

  return <AuthzContext.Provider value={value}>{children}</AuthzContext.Provider>;
}

/**
 * Hook to access authorization context
 */
export function useAuthz(): AuthzContextValue {
  const context = useContext(AuthzContext);
  if (!context) {
    throw new Error('useAuthz must be used within an AuthzProvider');
  }
  return context;
}

/**
 * Hook to check a single permission
 */
export function usePermission(permissionKey: string): boolean {
  const { hasPermission, isLoading } = useAuthz();
  if (isLoading) return false;
  return hasPermission(permissionKey);
}

/**
 * Hook to check if any of multiple permissions are granted
 */
export function useAnyPermission(permissionKeys: string[]): boolean {
  const { hasAnyPermission, isLoading } = useAuthz();
  if (isLoading) return false;
  return hasAnyPermission(permissionKeys);
}

/**
 * Hook to check if all of multiple permissions are granted
 */
export function useAllPermissions(permissionKeys: string[]): boolean {
  const { hasAllPermissions, isLoading } = useAuthz();
  if (isLoading) return false;
  return hasAllPermissions(permissionKeys);
}

/**
 * Hook to check if a module is enabled
 */
export function useModuleEnabled(moduleKey: string): boolean {
  const { isModuleEnabled, isLoading } = useAuthz();
  if (isLoading) return false;
  return isModuleEnabled(moduleKey);
}

/**
 * Hook to check if user is super admin
 */
export function useSuperAdmin(): boolean {
  const { isSuperAdmin, isLoading } = useAuthz();
  if (isLoading) return false;
  return isSuperAdmin;
}

/**
 * Match permission with wildcard support
 */
function matchPermission(pattern: string, permission: string): boolean {
  if (pattern === permission) return true;

  if (pattern.includes('*')) {
    // Convert wildcard pattern to regex
    const regexPattern = pattern
      .replace(/\./g, '\\.')
      .replace(/\*/g, '.*');
    const regex = new RegExp(`^${regexPattern}$`);
    return regex.test(permission);
  }

  return false;
}

export default AuthzContext;
