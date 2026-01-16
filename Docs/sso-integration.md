# SSO Integration Guide

## Overview

The Noveris AI platform supports Single Sign-On (SSO) via three protocols:

- **OIDC** (OpenID Connect) - Recommended for most use cases
- **OAuth2** - For providers without OIDC support
- **SAML** - For enterprise IdPs like ADFS, Okta, OneLogin

## Supported Identity Providers

| Provider | Protocols | Notes |
|----------|-----------|-------|
| Google Workspace | OIDC | Auto-discovery |
| Microsoft Entra ID (Azure AD) | OIDC, SAML | Both supported |
| Okta | OIDC, SAML | Both supported |
| Auth0 | OIDC | Auto-discovery |
| Keycloak | OIDC, SAML | Both supported |
| AWS Cognito | OIDC | Custom domain recommended |
| OneLogin | OIDC, SAML | Both supported |
| PingIdentity | OIDC, SAML | Both supported |
| ADFS | SAML | Windows Server |
| Generic OIDC | OIDC | Any compliant provider |
| Generic SAML | SAML | Any SAML 2.0 IdP |

## OIDC Configuration

### Prerequisites

1. Register an application in your IdP
2. Note the Client ID and Client Secret
3. Configure the redirect URI

### Redirect URI

```
https://your-domain/api/v1/sso/callback/oidc/{provider_id}
```

Replace `{provider_id}` with the UUID assigned when creating the provider.

### Configuration Options

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Internal provider identifier |
| `display_name` | No | Name shown on login button |
| `client_id` | Yes | Application client ID |
| `client_secret` | Yes | Application client secret |
| `issuer_url` | Conditional | For auto-discovery (preferred) |
| `authorization_url` | Conditional | Required if no issuer_url |
| `token_url` | Conditional | Required if no issuer_url |
| `userinfo_url` | No | For user info endpoint |
| `jwks_uri` | Conditional | Required if no issuer_url |
| `scopes` | No | Default: `openid profile email` |
| `email_domains` | No | Restrict to specific domains |

### Auto-Discovery (Recommended)

If your IdP supports OIDC Discovery, provide only the `issuer_url`:

```json
{
  "name": "google",
  "display_name": "Sign in with Google",
  "client_id": "your-client-id.apps.googleusercontent.com",
  "client_secret": "your-client-secret",
  "issuer_url": "https://accounts.google.com"
}
```

The system will automatically fetch configuration from:
`{issuer_url}/.well-known/openid-configuration`

### Manual Configuration

For providers without discovery support:

```json
{
  "name": "custom-oidc",
  "display_name": "Corporate SSO",
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "authorization_url": "https://idp.example.com/authorize",
  "token_url": "https://idp.example.com/token",
  "userinfo_url": "https://idp.example.com/userinfo",
  "jwks_uri": "https://idp.example.com/.well-known/jwks.json",
  "scopes": "openid profile email"
}
```

### PKCE Support

PKCE (Proof Key for Code Exchange) is automatically enabled for all OIDC flows:
- `code_verifier`: Random 43-character string
- `code_challenge`: SHA256 hash of verifier, base64url encoded
- `code_challenge_method`: S256

## OAuth2 Configuration

Use OAuth2 when OIDC is not available.

### Configuration Options

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Internal provider identifier |
| `display_name` | No | Name shown on login button |
| `client_id` | Yes | Application client ID |
| `client_secret` | Yes | Application client secret |
| `authorization_url` | Yes | OAuth2 authorization endpoint |
| `token_url` | Yes | OAuth2 token endpoint |
| `userinfo_url` | No | User profile endpoint |
| `scopes` | No | Requested scopes |

### Example: GitHub OAuth2

```json
{
  "name": "github",
  "display_name": "Sign in with GitHub",
  "client_id": "your-github-client-id",
  "client_secret": "your-github-client-secret",
  "authorization_url": "https://github.com/login/oauth/authorize",
  "token_url": "https://github.com/login/oauth/access_token",
  "userinfo_url": "https://api.github.com/user",
  "scopes": "user:email"
}
```

## SAML Configuration

### Prerequisites

1. Configure SP metadata in your IdP
2. Obtain IdP metadata or certificate

### Assertion Consumer Service (ACS) URL

```
https://your-domain/api/v1/sso/acs/{provider_id}
```

### Service Provider Entity ID

```
https://your-domain/api/v1/sso/metadata/{provider_id}
```

### Configuration Options

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Internal provider identifier |
| `display_name` | No | Name shown on login button |
| `idp_entity_id` | Yes | IdP Entity ID |
| `idp_sso_url` | Yes | IdP SSO URL |
| `idp_certificate` | Yes | IdP X.509 certificate (PEM) |
| `sp_entity_id` | No | Auto-generated if not provided |
| `email_attribute` | No | SAML attribute for email |
| `name_attribute` | No | SAML attribute for name |

### Example: Okta SAML

```json
{
  "name": "okta-saml",
  "display_name": "Sign in with Okta",
  "idp_entity_id": "http://www.okta.com/exk123abc",
  "idp_sso_url": "https://dev-123456.okta.com/app/dev-123456_noveris_1/exk123abc/sso/saml",
  "idp_certificate": "-----BEGIN CERTIFICATE-----\nMIIDpD...\n-----END CERTIFICATE-----",
  "email_attribute": "email",
  "name_attribute": "displayName"
}
```

### IdP Metadata URL

If your IdP provides a metadata URL, the system can fetch configuration automatically:

```json
{
  "name": "enterprise-saml",
  "display_name": "Corporate SSO",
  "metadata_url": "https://idp.example.com/metadata"
}
```

## Security Best Practices

### Email Domain Restrictions

Restrict SSO to specific email domains:

```json
{
  "email_domains": ["example.com", "corp.example.com"]
}
```

Users with emails outside these domains will be rejected.

### State Token Protection

The system uses state tokens to prevent CSRF attacks:
- Random 32-byte token generated per login attempt
- Stored in database with TTL (default: 10 minutes)
- Validated on callback

### Nonce Validation (OIDC)

For OIDC providers, a nonce is included in the ID token to prevent replay attacks.

### PKCE (OIDC/OAuth2)

PKCE protects against authorization code interception:
- Always enabled for OIDC
- Recommended for OAuth2 when supported

## Troubleshooting

### Common Issues

**1. Redirect URI Mismatch**

Error: "redirect_uri_mismatch" or "invalid redirect URI"

Solution: Ensure the redirect URI in your IdP configuration exactly matches:
```
https://your-domain/api/v1/sso/callback/oidc/{provider_id}
```

**2. Invalid State**

Error: "Invalid or expired state token"

Causes:
- User took too long to complete SSO (>10 minutes)
- User opened multiple login tabs
- CSRF attack attempt

Solution: Retry the login flow

**3. Missing Email Claim**

Error: "No email found in user info"

Causes:
- Scopes don't include email
- User hasn't verified email with IdP
- Wrong attribute mapping

Solution:
- Add `email` scope
- Check IdP user profile
- Configure `email_attribute` for SAML

**4. Certificate Validation Failed (SAML)**

Error: "Signature validation failed"

Causes:
- Wrong certificate
- Certificate expired
- IdP certificate rotated

Solution: Update the IdP certificate in provider configuration

### Debug Logging

Enable verbose SSO logging:

```env
LOG_LEVEL=DEBUG
SSO_DEBUG=true
```

Logs will include:
- Token exchange requests/responses
- User info responses
- SAML assertions (decoded)

## IdP-Specific Guides

### Google Workspace

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create OAuth 2.0 credentials
3. Add authorized redirect URI
4. Enable Google+ API (for user profile)

```json
{
  "name": "google",
  "display_name": "Sign in with Google",
  "issuer_url": "https://accounts.google.com",
  "client_id": "xxx.apps.googleusercontent.com",
  "client_secret": "xxx",
  "scopes": "openid email profile"
}
```

### Microsoft Entra ID (Azure AD)

1. Go to [Azure Portal](https://portal.azure.com) > App registrations
2. Create new registration
3. Add redirect URI (Web platform)
4. Create client secret

```json
{
  "name": "azure-ad",
  "display_name": "Sign in with Microsoft",
  "issuer_url": "https://login.microsoftonline.com/{tenant-id}/v2.0",
  "client_id": "xxx",
  "client_secret": "xxx",
  "scopes": "openid email profile"
}
```

### Okta

1. Go to Okta Admin Console > Applications
2. Create OIDC Web Application
3. Set redirect URIs

```json
{
  "name": "okta",
  "display_name": "Sign in with Okta",
  "issuer_url": "https://dev-xxx.okta.com",
  "client_id": "xxx",
  "client_secret": "xxx"
}
```

### Keycloak

1. Create new client in realm
2. Set access type to confidential
3. Configure valid redirect URIs

```json
{
  "name": "keycloak",
  "display_name": "Sign in with Keycloak",
  "issuer_url": "https://keycloak.example.com/realms/your-realm",
  "client_id": "noveris",
  "client_secret": "xxx"
}
```
