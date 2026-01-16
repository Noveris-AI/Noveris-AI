/**
 * Settings API client
 */

import axios from 'axios';
import type {
  AuthPolicy,
  AuthPolicyUpdateRequest,
  SSOProvider,
  SSOProviderCreateRequest,
  SSOProviderUpdateRequest,
  SecurityPolicy,
  SecurityPolicyUpdateRequest,
  BrandingSettings,
  BrandingUpdateRequest,
  UserProfile,
  UserProfileUpdateRequest,
  FeatureFlag,
  AuditLog,
  SettingsCatalog,
  PublicSSOProvider,
  AuthDomain,
  ScopeType,
} from './types';

const API_BASE = '/api/v1/settings';

// ===========================================
// Settings Catalog
// ===========================================

export async function getSettingsCatalog(): Promise<SettingsCatalog> {
  const response = await axios.get(`${API_BASE}/catalog`);
  return response.data;
}

// ===========================================
// Auth Policy
// ===========================================

export async function getAuthPolicy(
  domain: AuthDomain,
  scopeType: ScopeType = 'system',
  scopeId?: string
): Promise<AuthPolicy> {
  const params = new URLSearchParams({ domain, scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.get(`${API_BASE}/auth-policy?${params}`);
  return response.data;
}

export async function updateAuthPolicy(
  domain: AuthDomain,
  data: AuthPolicyUpdateRequest,
  scopeType: ScopeType = 'system',
  scopeId?: string
): Promise<AuthPolicy> {
  const params = new URLSearchParams({ domain, scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.put(`${API_BASE}/auth-policy?${params}`, data);
  return response.data;
}

// ===========================================
// SSO Providers
// ===========================================

export async function getSSOProviders(
  domain: AuthDomain,
  scopeType: ScopeType = 'system',
  scopeId?: string,
  enabledOnly: boolean = false
): Promise<{ providers: SSOProvider[]; total: number }> {
  const params = new URLSearchParams({
    domain,
    scope_type: scopeType,
    enabled_only: String(enabledOnly),
  });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.get(`${API_BASE}/sso/providers?${params}`);
  return response.data;
}

export async function getSSOProvider(providerId: string): Promise<SSOProvider> {
  const response = await axios.get(`${API_BASE}/sso/providers/${providerId}`);
  return response.data;
}

export async function createSSOProvider(
  domain: AuthDomain,
  data: SSOProviderCreateRequest,
  scopeType: ScopeType = 'system',
  scopeId?: string
): Promise<SSOProvider> {
  const params = new URLSearchParams({ domain, scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.post(`${API_BASE}/sso/providers?${params}`, data);
  return response.data;
}

export async function updateSSOProvider(
  providerId: string,
  data: SSOProviderUpdateRequest
): Promise<SSOProvider> {
  const response = await axios.put(`${API_BASE}/sso/providers/${providerId}`, data);
  return response.data;
}

export async function deleteSSOProvider(providerId: string): Promise<void> {
  await axios.delete(`${API_BASE}/sso/providers/${providerId}`);
}

// ===========================================
// Security Policy
// ===========================================

export async function getSecurityPolicy(
  scopeType: ScopeType = 'system',
  scopeId?: string
): Promise<SecurityPolicy> {
  const params = new URLSearchParams({ scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.get(`${API_BASE}/security?${params}`);
  return response.data;
}

export async function updateSecurityPolicy(
  data: SecurityPolicyUpdateRequest,
  scopeType: ScopeType = 'system',
  scopeId?: string
): Promise<SecurityPolicy> {
  const params = new URLSearchParams({ scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.put(`${API_BASE}/security?${params}`, data);
  return response.data;
}

// ===========================================
// Branding
// ===========================================

export async function getBranding(
  scopeType: ScopeType = 'system',
  scopeId?: string
): Promise<BrandingSettings> {
  const params = new URLSearchParams({ scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.get(`${API_BASE}/branding?${params}`);
  return response.data;
}

export async function updateBranding(
  data: BrandingUpdateRequest,
  scopeType: ScopeType = 'system',
  scopeId?: string
): Promise<BrandingSettings> {
  const params = new URLSearchParams({ scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.put(`${API_BASE}/branding?${params}`, data);
  return response.data;
}

export async function uploadLogo(file: File, scopeType: ScopeType = 'system', scopeId?: string): Promise<BrandingSettings> {
  const formData = new FormData();
  formData.append('file', file);

  const params = new URLSearchParams({ scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.post(`${API_BASE}/branding/logo?${params}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function uploadFavicon(file: File, scopeType: ScopeType = 'system', scopeId?: string): Promise<BrandingSettings> {
  const formData = new FormData();
  formData.append('file', file);

  const params = new URLSearchParams({ scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.post(`${API_BASE}/branding/favicon?${params}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

// ===========================================
// User Profile
// ===========================================

export async function getMyProfile(): Promise<UserProfile> {
  const response = await axios.get(`${API_BASE}/profile/me`);
  return response.data;
}

export async function updateMyProfile(data: UserProfileUpdateRequest): Promise<UserProfile> {
  const response = await axios.patch(`${API_BASE}/profile/me`, data);
  return response.data;
}

export async function uploadAvatar(file: File): Promise<UserProfile> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await axios.post(`${API_BASE}/profile/me/avatar`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await axios.post(`${API_BASE}/profile/me/change-password`, {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

// ===========================================
// Feature Flags
// ===========================================

export async function getFeatureFlags(
  scopeType: ScopeType = 'system',
  scopeId?: string
): Promise<{ flags: FeatureFlag[]; total: number }> {
  const params = new URLSearchParams({ scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.get(`${API_BASE}/features?${params}`);
  return response.data;
}

export async function getFeatureFlag(
  flagKey: string,
  scopeType: ScopeType = 'system',
  scopeId?: string
): Promise<FeatureFlag> {
  const params = new URLSearchParams({ scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.get(`${API_BASE}/features/${flagKey}?${params}`);
  return response.data;
}

export async function setFeatureFlag(
  flagKey: string,
  enabled: boolean,
  description?: string,
  scopeType: ScopeType = 'system',
  scopeId?: string
): Promise<FeatureFlag> {
  const params = new URLSearchParams({ scope_type: scopeType });
  if (scopeId) params.set('scope_id', scopeId);

  const response = await axios.put(`${API_BASE}/features/${flagKey}?${params}`, {
    enabled,
    description,
  });
  return response.data;
}

// ===========================================
// Audit Logs
// ===========================================

export async function getAuditLogs(
  options: {
    scopeType?: ScopeType;
    scopeId?: string;
    resourceType?: string;
    limit?: number;
    offset?: number;
  } = {}
): Promise<{ logs: AuditLog[]; total: number }> {
  const params = new URLSearchParams();
  if (options.scopeType) params.set('scope_type', options.scopeType);
  if (options.scopeId) params.set('scope_id', options.scopeId);
  if (options.resourceType) params.set('resource_type', options.resourceType);
  if (options.limit) params.set('limit', String(options.limit));
  if (options.offset) params.set('offset', String(options.offset));

  const response = await axios.get(`${API_BASE}/audit-logs?${params}`);
  return response.data;
}

// ===========================================
// Public SSO Providers (for login page)
// ===========================================

export async function getPublicSSOProviders(domain: AuthDomain): Promise<{ providers: PublicSSOProvider[] }> {
  const response = await axios.get(`/api/v1/sso/${domain}/providers`);
  return response.data;
}
