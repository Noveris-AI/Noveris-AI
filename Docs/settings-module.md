# Settings Module Documentation

## Overview

The Settings module provides comprehensive configuration management for the Noveris AI platform. It supports:

- **Authentication Settings**: Multi-domain authentication policies (admin, members, webapp)
- **SSO Integration**: OIDC, OAuth2, and SAML providers
- **Security Policies**: Password policies, IP access control, egress control
- **Branding**: Logo, favicon, brand name, colors
- **Notifications**: SMTP, webhooks, enterprise IM (Slack, DingTalk, Feishu, WeChat)
- **Feature Flags**: Platform feature toggles
- **Profile Management**: User avatar, nickname, locale, timezone

## Architecture

### Settings Scope Hierarchy

Settings follow a 3-level inheritance model:

```
System (global defaults)
   └── Tenant (organization overrides)
       └── User (personal preferences)
```

When resolving a setting value:
1. Check User scope first
2. Fall back to Tenant scope
3. Fall back to System scope

### Database Schema

Key tables:

| Table | Purpose |
|-------|---------|
| `settings_kv` | Generic key-value settings storage |
| `sso_providers` | SSO provider configurations |
| `auth_policies` | Authentication policies per domain |
| `user_profiles` | User profile data (avatar, nickname, locale) |
| `branding_settings` | Brand customization |
| `notification_channels` | Notification channel configs |
| `security_policies` | Password and access policies |
| `feature_flags` | Feature toggles |
| `settings_audit_logs` | Audit trail for changes |
| `sso_state_tokens` | CSRF protection for SSO flows |

### Encryption

Sensitive settings (passwords, secrets, API keys) are encrypted using Fernet symmetric encryption:

- Key derivation: PBKDF2 with SHA256
- Encryption: AES-128 in CBC mode with PKCS7 padding
- Key rotation: Supported via MultiFernet

Configuration:
```env
SETTINGS_ENCRYPTION_KEY=your-secret-key-here
SETTINGS_ENCRYPTION_SALT=your-salt-here
```

## API Reference

### Authentication Policies

```
GET    /api/v1/settings/auth-policy/{domain}
PUT    /api/v1/settings/auth-policy/{domain}
```

Domains: `admin`, `members`, `webapp`

Example response:
```json
{
  "domain": "admin",
  "email_password_enabled": true,
  "email_code_enabled": false,
  "sso_enabled": true,
  "session_timeout_days": 1,
  "self_signup_enabled": false,
  "auto_create_admin_on_first_sso": false
}
```

### SSO Providers

```
GET    /api/v1/settings/sso/providers/{domain}
POST   /api/v1/settings/sso/providers/{domain}
PUT    /api/v1/settings/sso/providers/{domain}/{provider_id}
DELETE /api/v1/settings/sso/providers/{domain}/{provider_id}
```

Provider types: `oidc`, `oauth2`, `saml`

### Security Policies

```
GET    /api/v1/settings/security
PUT    /api/v1/settings/security
```

### Branding

```
GET    /api/v1/settings/branding
PUT    /api/v1/settings/branding
POST   /api/v1/settings/branding/logo
POST   /api/v1/settings/branding/favicon
```

### User Profile

```
GET    /api/v1/settings/profile
PUT    /api/v1/settings/profile
POST   /api/v1/settings/profile/avatar
POST   /api/v1/settings/profile/password
```

### Feature Flags

```
GET    /api/v1/settings/features
PUT    /api/v1/settings/features/{key}
```

### Audit Logs

```
GET    /api/v1/settings/audit-logs
```

Query parameters:
- `action`: Filter by action type
- `actor_id`: Filter by actor
- `resource_type`: Filter by resource type
- `from_date`, `to_date`: Date range
- `limit`, `offset`: Pagination

## SSO Integration Guide

### OIDC Provider Setup

1. Register your application with the IdP
2. Configure callback URL: `https://your-domain/api/v1/sso/callback/oidc/{provider_id}`
3. Obtain client ID and secret
4. Configure in Settings:
   - Issuer URL (for auto-discovery)
   - OR manual endpoints: authorization, token, userinfo, jwks
   - Scopes: `openid profile email` (minimum)

### OAuth2 Provider Setup

Similar to OIDC but requires manual endpoint configuration:
- Authorization URL
- Token URL
- UserInfo URL (optional)
- Scopes

### SAML Provider Setup

1. Exchange metadata with IdP
2. Configure in Settings:
   - IdP Metadata URL or certificate
   - Entity ID
   - ACS URL: `https://your-domain/api/v1/sso/acs/{provider_id}`

## Security Considerations

### At-least-one-login-method Rule

The system prevents disabling all login methods to avoid lockout:
- Cannot disable email/password if SSO is disabled
- Warning when disabling the last authentication method
- `confirm_risk` flag required to override

### Auto-Create Admin Protection

The `auto_create_admin_on_first_sso` feature:
- Only available with trusted SSO providers
- Should be combined with email domain restrictions
- Shows security warning in UI

### IP Access Control

- IP allowlist: Only listed IPs can access
- IP blocklist: Listed IPs are denied
- CIDR notation supported (e.g., `192.168.1.0/24`)

### Egress Control

- Controls outbound network connections
- Whitelist domains for integrations
- Helps prevent data exfiltration

## Frontend Components

### Pages

| Page | Route | Description |
|------|-------|-------------|
| AuthSettingsPage | `/settings` | Authentication policies and SSO |
| ProfileSettingsPage | `/settings/profile` | User profile management |
| BrandingSettingsPage | `/settings/branding` | Brand customization |
| NotificationsSettingsPage | `/settings/notifications` | Notification channels |
| SecuritySettingsPage | `/settings/security` | Security policies |
| AdvancedSettingsPage | `/settings/advanced` | Feature flags, debug settings |

### Components

- `SettingCard`: Card container for settings sections
- `SettingRow`: Row with toggle switch
- `SSOProviderModal`: Modal for SSO provider configuration

### Hooks

All settings use TanStack Query for data fetching:

```typescript
// Auth policies
useAuthPolicy(domain)
useUpdateAuthPolicy(domain)

// SSO providers
useSSOProviders(domain)
useCreateSSOProvider(domain)
useUpdateSSOProvider(domain)
useDeleteSSOProvider(domain)

// Security
useSecurityPolicy()
useUpdateSecurityPolicy()

// Branding
useBrandingSettings()
useUpdateBrandingSettings()

// Profile
useUserProfile()
useUpdateUserProfile()
useChangePassword()

// Features
useFeatureFlags()
useUpdateFeatureFlag()

// Audit
useAuditLogs(params)
```

## Configuration

### Environment Variables

```env
# Encryption
SETTINGS_ENCRYPTION_KEY=your-encryption-key
SETTINGS_ENCRYPTION_SALT=your-salt

# SSO
SSO_CALLBACK_BASE_URL=https://your-domain/api/v1/sso
SSO_STATE_TOKEN_TTL=600  # seconds

# Session
SESSION_COOKIE_NAME=session_id
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=lax
```

## Migration

Run the migration to create settings tables:

```bash
cd Backend
alembic upgrade head
```

Migration file: `alembic_migrations/versions/20260117_0001_add_settings_tables.py`

## Testing

### Unit Tests

```bash
pytest Backend/tests/unit/settings/
```

### Integration Tests

```bash
pytest Backend/tests/integration/settings/
```

### E2E Tests

```bash
cd Frontend
npm run test:e2e -- --spec "cypress/e2e/settings/**"
```
