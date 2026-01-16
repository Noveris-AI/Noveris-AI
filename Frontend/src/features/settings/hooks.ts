/**
 * Settings React Query hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from './api';
import type {
  AuthDomain,
  ScopeType,
  AuthPolicyUpdateRequest,
  SSOProviderCreateRequest,
  SSOProviderUpdateRequest,
  SecurityPolicyUpdateRequest,
  BrandingUpdateRequest,
  UserProfileUpdateRequest,
} from './types';

// Query keys
export const settingsKeys = {
  all: ['settings'] as const,
  catalog: () => [...settingsKeys.all, 'catalog'] as const,
  authPolicy: (domain: AuthDomain, scopeType: ScopeType, scopeId?: string) =>
    [...settingsKeys.all, 'auth-policy', domain, scopeType, scopeId] as const,
  ssoProviders: (domain: AuthDomain, scopeType: ScopeType, scopeId?: string) =>
    [...settingsKeys.all, 'sso-providers', domain, scopeType, scopeId] as const,
  ssoProvider: (id: string) => [...settingsKeys.all, 'sso-provider', id] as const,
  securityPolicy: (scopeType: ScopeType, scopeId?: string) =>
    [...settingsKeys.all, 'security', scopeType, scopeId] as const,
  branding: (scopeType: ScopeType, scopeId?: string) =>
    [...settingsKeys.all, 'branding', scopeType, scopeId] as const,
  profile: () => [...settingsKeys.all, 'profile'] as const,
  featureFlag: (key: string, scopeType: ScopeType, scopeId?: string) =>
    [...settingsKeys.all, 'feature', key, scopeType, scopeId] as const,
  auditLogs: (options: Record<string, unknown>) =>
    [...settingsKeys.all, 'audit-logs', options] as const,
  publicSSOProviders: (domain: AuthDomain) =>
    [...settingsKeys.all, 'public-sso', domain] as const,
};

// ===========================================
// Settings Catalog
// ===========================================

export function useSettingsCatalog() {
  return useQuery({
    queryKey: settingsKeys.catalog(),
    queryFn: api.getSettingsCatalog,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// ===========================================
// Auth Policy
// ===========================================

export function useAuthPolicy(
  domain: AuthDomain,
  scopeType: ScopeType = 'system',
  scopeId?: string
) {
  return useQuery({
    queryKey: settingsKeys.authPolicy(domain, scopeType, scopeId),
    queryFn: () => api.getAuthPolicy(domain, scopeType, scopeId),
  });
}

export function useUpdateAuthPolicy(
  domain: AuthDomain,
  scopeType: ScopeType = 'system',
  scopeId?: string
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AuthPolicyUpdateRequest) =>
      api.updateAuthPolicy(domain, data, scopeType, scopeId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.authPolicy(domain, scopeType, scopeId),
      });
    },
  });
}

// ===========================================
// SSO Providers
// ===========================================

export function useSSOProviders(
  domain: AuthDomain,
  scopeType: ScopeType = 'system',
  scopeId?: string,
  enabledOnly: boolean = false
) {
  return useQuery({
    queryKey: settingsKeys.ssoProviders(domain, scopeType, scopeId),
    queryFn: () => api.getSSOProviders(domain, scopeType, scopeId, enabledOnly),
  });
}

export function useSSOProvider(providerId: string) {
  return useQuery({
    queryKey: settingsKeys.ssoProvider(providerId),
    queryFn: () => api.getSSOProvider(providerId),
    enabled: !!providerId,
  });
}

export function useCreateSSOProvider(
  domain: AuthDomain,
  scopeType: ScopeType = 'system',
  scopeId?: string
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SSOProviderCreateRequest) =>
      api.createSSOProvider(domain, data, scopeType, scopeId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.ssoProviders(domain, scopeType, scopeId),
      });
    },
  });
}

export function useUpdateSSOProvider(
  domain: AuthDomain,
  scopeType: ScopeType = 'system',
  scopeId?: string
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SSOProviderUpdateRequest }) =>
      api.updateSSOProvider(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.ssoProviders(domain, scopeType, scopeId),
      });
      queryClient.invalidateQueries({
        queryKey: settingsKeys.ssoProvider(id),
      });
    },
  });
}

export function useDeleteSSOProvider(
  domain: AuthDomain,
  scopeType: ScopeType = 'system',
  scopeId?: string
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.deleteSSOProvider(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.ssoProviders(domain, scopeType, scopeId),
      });
    },
  });
}

// ===========================================
// Security Policy
// ===========================================

export function useSecurityPolicy(scopeType: ScopeType = 'system', scopeId?: string) {
  return useQuery({
    queryKey: settingsKeys.securityPolicy(scopeType, scopeId),
    queryFn: () => api.getSecurityPolicy(scopeType, scopeId),
  });
}

export function useUpdateSecurityPolicy(scopeType: ScopeType = 'system', scopeId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SecurityPolicyUpdateRequest) =>
      api.updateSecurityPolicy(data, scopeType, scopeId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.securityPolicy(scopeType, scopeId),
      });
    },
  });
}

// ===========================================
// Branding
// ===========================================

export function useBranding(scopeType: ScopeType = 'system', scopeId?: string) {
  return useQuery({
    queryKey: settingsKeys.branding(scopeType, scopeId),
    queryFn: () => api.getBranding(scopeType, scopeId),
  });
}

export function useUpdateBranding(scopeType: ScopeType = 'system', scopeId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: BrandingUpdateRequest) =>
      api.updateBranding(data, scopeType, scopeId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.branding(scopeType, scopeId),
      });
    },
  });
}

// Aliases for consistency with page imports
export const useBrandingSettings = useBranding;
export const useUpdateBrandingSettings = useUpdateBranding;

// ===========================================
// User Profile
// ===========================================

export function useMyProfile() {
  return useQuery({
    queryKey: settingsKeys.profile(),
    queryFn: api.getMyProfile,
  });
}

export function useUpdateMyProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UserProfileUpdateRequest) => api.updateMyProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.profile(),
      });
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: ({ current_password, new_password }: { current_password: string; new_password: string }) =>
      api.changePassword(current_password, new_password),
  });
}

// Aliases for consistency with page imports
export const useUserProfile = useMyProfile;
export const useUpdateUserProfile = useUpdateMyProfile;

// ===========================================
// Feature Flags
// ===========================================

export function useFeatureFlags(scopeType: ScopeType = 'system', scopeId?: string) {
  return useQuery({
    queryKey: [...settingsKeys.all, 'features', scopeType, scopeId],
    queryFn: () => api.getFeatureFlags(scopeType, scopeId),
  });
}

export function useFeatureFlag(
  flagKey: string,
  scopeType: ScopeType = 'system',
  scopeId?: string
) {
  return useQuery({
    queryKey: settingsKeys.featureFlag(flagKey, scopeType, scopeId),
    queryFn: () => api.getFeatureFlag(flagKey, scopeType, scopeId),
  });
}

export function useSetFeatureFlag(scopeType: ScopeType = 'system', scopeId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ flagKey, enabled, description }: { flagKey: string; enabled: boolean; description?: string }) =>
      api.setFeatureFlag(flagKey, enabled, description, scopeType, scopeId),
    onSuccess: (_, { flagKey }) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.featureFlag(flagKey, scopeType, scopeId),
      });
      queryClient.invalidateQueries({
        queryKey: [...settingsKeys.all, 'features', scopeType, scopeId],
      });
    },
  });
}

// Alias for consistency with page imports
export function useUpdateFeatureFlag(scopeType: ScopeType = 'system', scopeId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      api.setFeatureFlag(key, enabled, undefined, scopeType, scopeId),
    onSuccess: (_, { key }) => {
      queryClient.invalidateQueries({
        queryKey: settingsKeys.featureFlag(key, scopeType, scopeId),
      });
      queryClient.invalidateQueries({
        queryKey: [...settingsKeys.all, 'features', scopeType, scopeId],
      });
    },
  });
}

// ===========================================
// Audit Logs
// ===========================================

export function useAuditLogs(options: {
  scopeType?: ScopeType;
  scopeId?: string;
  resourceType?: string;
  limit?: number;
  offset?: number;
} = {}) {
  return useQuery({
    queryKey: settingsKeys.auditLogs(options),
    queryFn: () => api.getAuditLogs(options),
  });
}

// ===========================================
// Public SSO Providers
// ===========================================

export function usePublicSSOProviders(domain: AuthDomain) {
  return useQuery({
    queryKey: settingsKeys.publicSSOProviders(domain),
    queryFn: () => api.getPublicSSOProviders(domain),
  });
}
