/**
 * Settings feature types
 */

// Scope types
export type ScopeType = 'system' | 'tenant' | 'user';
export type AuthDomain = 'admin' | 'members' | 'webapp';
export type SSOProviderType = 'oidc' | 'oauth2' | 'saml';
export type NotificationChannelType = 'smtp' | 'webhook' | 'slack' | 'feishu' | 'wecom' | 'dingtalk';

// Auth Policy
export interface AuthPolicy {
  id: string;
  domain: AuthDomain;
  scope_type: ScopeType;
  scope_id?: string;
  email_password_enabled: boolean;
  email_code_enabled: boolean;
  sso_enabled: boolean;
  session_timeout_days: number;
  auto_create_admin_on_first_sso: boolean;
  auto_create_admin_email_domains?: string[];
  self_signup_enabled: boolean;
  signup_auto_create_personal_space: boolean;
  allowed_email_domains?: string[];
  updated_at?: string;
}

export interface AuthPolicyUpdateRequest {
  email_password_enabled?: boolean;
  email_code_enabled?: boolean;
  sso_enabled?: boolean;
  session_timeout_days?: number;
  auto_create_admin_on_first_sso?: boolean;
  auto_create_admin_email_domains?: string[];
  self_signup_enabled?: boolean;
  signup_auto_create_personal_space?: boolean;
  allowed_email_domains?: string[];
  confirm_risk?: boolean;
}

// SSO Provider
export interface SSOProvider {
  id: string;
  scope_type: ScopeType;
  scope_id?: string;
  domain: AuthDomain;
  provider_type: SSOProviderType;
  name: string;
  display_name?: string;
  icon?: string;
  enabled: boolean;
  order: number;
  config?: Record<string, unknown>;
  callback_url?: string;
  acs_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface SSOProviderCreateRequest {
  provider_type: SSOProviderType;
  name: string;
  display_name?: string;
  icon?: string;
  enabled?: boolean;
  config: Record<string, unknown>;
  secrets?: Record<string, unknown>;
}

export interface SSOProviderUpdateRequest {
  name?: string;
  display_name?: string;
  icon?: string;
  enabled?: boolean;
  order?: number;
  config?: Record<string, unknown>;
  secrets?: Record<string, unknown>;
}

// OIDC Config
export interface OIDCConfig {
  issuer_or_discovery_url: string;
  client_id: string;
  scopes?: string;
  use_pkce?: boolean;
  claim_mapping?: {
    email?: string;
    name?: string;
    groups?: string;
  };
}

// OAuth2 Config
export interface OAuth2Config {
  authorization_endpoint: string;
  token_endpoint: string;
  userinfo_endpoint: string;
  client_id: string;
  scopes?: string;
  use_pkce?: boolean;
  claim_mapping?: {
    id?: string;
    email?: string;
    name?: string;
    groups?: string;
  };
}

// SAML Config
export interface SAMLConfig {
  idp_sso_url: string;
  idp_entity_id?: string;
  sp_entity_id?: string;
  nameid_format?: string;
  attribute_mapping?: {
    email?: string;
    name?: string;
    groups?: string;
  };
}

// Security Policy
export interface SecurityPolicy {
  id: string;
  scope_type: ScopeType;
  scope_id?: string;
  session_idle_timeout_minutes: number;
  session_absolute_timeout_days: number;
  max_concurrent_sessions: number;
  force_logout_on_password_change: boolean;
  password_min_length: number;
  password_require_uppercase: boolean;
  password_require_lowercase: boolean;
  password_require_digit: boolean;
  password_require_special: boolean;
  password_history_count: number;
  password_expiry_days?: number;
  max_login_attempts: number;
  lockout_duration_minutes: number;
  ip_allowlist?: string[];
  ip_denylist?: string[];
  ip_access_control_enabled: boolean;
  audit_log_enabled: boolean;
  audit_log_retention_days: number;
  egress_enabled: boolean;
  egress_allowed_domains?: string[];
  updated_at?: string;
}

export interface SecurityPolicyUpdateRequest {
  session_idle_timeout_minutes?: number;
  session_absolute_timeout_days?: number;
  max_concurrent_sessions?: number;
  force_logout_on_password_change?: boolean;
  password_min_length?: number;
  password_require_uppercase?: boolean;
  password_require_lowercase?: boolean;
  password_require_digit?: boolean;
  password_require_special?: boolean;
  password_history_count?: number;
  password_expiry_days?: number;
  max_login_attempts?: number;
  lockout_duration_minutes?: number;
  ip_allowlist?: string[];
  ip_denylist?: string[];
  ip_access_control_enabled?: boolean;
  audit_log_enabled?: boolean;
  audit_log_retention_days?: number;
  egress_enabled?: boolean;
  egress_allowed_domains?: string[];
}

// Branding
export interface BrandingSettings {
  id: string;
  scope_type: ScopeType;
  scope_id?: string;
  brand_name?: string;
  logo_url?: string;
  favicon_url?: string;
  login_page_title?: string;
  dashboard_title?: string;
  browser_title_template?: string;
  login_background_url?: string;
  primary_color?: string;
  color_scheme_locked: boolean;
  updated_at?: string;
}

export interface BrandingUpdateRequest {
  brand_name?: string;
  login_page_title?: string;
  dashboard_title?: string;
  browser_title_template?: string;
  primary_color?: string;
}

// User Profile
export interface UserProfile {
  user_id: string;
  display_name?: string;
  avatar_url?: string;
  locale: string;
  timezone: string;
  preferences?: Record<string, unknown>;
  updated_at?: string;
}

export interface UserProfileUpdateRequest {
  display_name?: string;
  locale?: string;
  timezone?: string;
  preferences?: Record<string, unknown>;
}

// Feature Flag
export interface FeatureFlag {
  id: string;
  scope_type: ScopeType;
  scope_id?: string;
  flag_key: string;
  enabled: boolean;
  description?: string;
  metadata?: Record<string, unknown>;
  updated_at?: string;
}

// Audit Log
export interface AuditLog {
  id: string;
  scope_type: ScopeType;
  scope_id?: string;
  actor_id: string;
  actor_email?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  resource_key?: string;
  old_value?: Record<string, unknown>;
  new_value?: Record<string, unknown>;
  ip_address?: string;
  created_at: string;
}

// Notification Channel
export interface NotificationChannel {
  id: string;
  scope_type: ScopeType;
  scope_id?: string;
  channel_type: NotificationChannelType;
  name: string;
  enabled: boolean;
  config?: Record<string, unknown>;
  last_test_at?: string;
  last_test_success?: boolean;
  created_at?: string;
  updated_at?: string;
}

// Settings Catalog
export interface SettingDefinition {
  key: string;
  title: string;
  title_i18n?: string;
  description?: string;
  description_i18n?: string;
  category: string;
  type: 'string' | 'boolean' | 'number' | 'json' | 'select' | 'multiselect';
  default?: unknown;
  options?: Array<{ value: string; label: string }>;
  validation?: Record<string, unknown>;
  sensitive: boolean;
  permission_read: string;
  permission_write: string;
  ui_hints?: Record<string, unknown>;
}

export interface SettingsCategory {
  key: string;
  title: string;
  title_i18n?: string;
  order: number;
}

export interface SettingsCatalog {
  categories: SettingsCategory[];
  settings: SettingDefinition[];
}

// Public SSO Provider (for login page)
export interface PublicSSOProvider {
  id: string;
  name: string;
  display_name: string;
  icon?: string;
  provider_type: SSOProviderType;
  login_url: string;
}
