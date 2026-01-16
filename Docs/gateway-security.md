# AI Gateway Security

This document outlines the security measures implemented in the AI Gateway module.

## 1. Authentication

### API Key Authentication

External clients authenticate using Bearer tokens:

```
Authorization: Bearer sk-xxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Key Generation:**
- Keys use the format: `sk-<prefix>-<secret>`
- Prefix: 8 hex characters (for lookup)
- Secret: 32 hex characters (for verification)
- Keys are hashed using bcrypt (12 rounds) before storage
- Only the prefix is stored in plaintext for display

**Key Verification:**
1. Extract prefix from incoming key
2. Look up key record by prefix
3. Verify full key against bcrypt hash
4. Check if key is enabled and not expired
5. Validate access permissions

### Session Authentication (Control Plane)

Admin APIs use the platform's existing session-based authentication:
- HTTP-only cookies
- CSRF protection
- Session TTL: 24 hours

## 2. Authorization

### Access Control

Each API key has:
- `allowed_models`: List of model patterns the key can access (wildcards supported)
- `allowed_endpoints`: List of endpoint patterns the key can access
- Empty lists mean "allow all"

**Pattern Matching:**
- Supports glob patterns: `openai/*`, `*/gpt-4*`
- Evaluated using `fnmatch`

### Rate Limiting

Redis-based sliding window rate limiting:
- Requests per minute/hour/day
- Tokens per minute/day
- Per-key, per-tenant, and global limits

### Quota Management

Persistent usage quotas:
- Maximum tokens per period
- Maximum requests per period
- Reset intervals: daily, weekly, monthly

## 3. SSRF Protection

### Blocked Networks

The gateway blocks requests to:
- Loopback addresses (127.0.0.0/8, ::1)
- Private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Link-local addresses (169.254.0.0/16, fe80::/10)
- Cloud metadata endpoints (169.254.169.254)
- Multicast and reserved ranges

### DNS Validation

- All hostnames are resolved before connection
- Resolved IPs are validated against blocked ranges
- Prevents DNS rebinding attacks

### Redirect Validation

- Redirects are validated against SSRF rules
- Cross-origin redirects require explicit allowlist
- Maximum redirect count: 5

### Upstream Allowlists

Each upstream can define:
- `allow_hosts`: Allowed hostnames
- `allow_cidrs`: Allowed IP ranges

## 4. Credential Security

### Encryption at Rest

Upstream credentials are encrypted using Fernet (AES-128-CBC with HMAC-SHA256):

```python
from cryptography.fernet import Fernet

# Generate key (store in GATEWAY_SECRET_ENCRYPTION_KEY)
key = Fernet.generate_key()

# Encrypt
fernet = Fernet(key)
ciphertext = fernet.encrypt(plaintext.encode())

# Decrypt (only in memory, never logged)
plaintext = fernet.decrypt(ciphertext).decode()
```

### Key Management

- Encryption key stored in environment variable
- Key rotation supported via `key_version` field
- Credentials never logged or exposed in API responses

## 5. Request Security

### Input Validation

- Request body size limit: configurable (default 10MB)
- Schema validation using Pydantic
- Content-Type enforcement

### Header Injection Prevention

- Headers are sanitized before forwarding
- No user-controlled header names
- Authorization headers are never logged

### Request Smuggling Prevention

- Proper Content-Length handling
- No HTTP/0.9 or HTTP/1.0 support in upstream
- Strict HTTP parsing

## 6. Logging Security

### Log Payload Modes

| Mode | Description |
|------|-------------|
| `none` | No request/response logging |
| `metadata_only` | Only metadata (tokens, latency, etc.) |
| `sampled` | Sample X% of requests |
| `full_with_redaction` | Full payload with sensitive field redaction |

### Redacted Fields

These fields are automatically redacted from logs:
- `Authorization` header
- `api_key` in request body
- `password` fields
- Image/audio binary data
- Custom patterns configurable

### Log Retention

- Configurable retention period (default: 30 days)
- Automatic cleanup of old logs
- Optional cold storage migration

## 7. Circuit Breaker

### State Machine

```
CLOSED (normal)
    │
    ▼ (failures >= threshold)
   OPEN (fail fast)
    │
    ▼ (after timeout)
HALF_OPEN (testing)
    │
    ├──▶ CLOSED (successes >= threshold)
    │
    └──▶ OPEN (any failure)
```

### Configuration

```python
{
    "failure_threshold": 5,      # Failures before opening
    "success_threshold": 3,      # Successes to close
    "timeout_seconds": 60,       # Time before half-open
    "half_open_max_requests": 3  # Test requests in half-open
}
```

## 8. TLS/HTTPS

### Upstream Connections

- All upstream connections use HTTPS by default
- TLS 1.2+ required
- Certificate validation enabled
- Optional: custom CA certificates

### Client Connections

- HTTPS enforced in production
- HSTS header set
- Secure cookie flags

## 9. Audit Trail

### Logged Events

- API key creation/deletion
- Upstream configuration changes
- Route policy changes
- Authentication failures
- Rate limit violations
- SSRF violations

### Log Format

```json
{
    "timestamp": "2026-01-16T00:00:00Z",
    "event_type": "api_key_created",
    "tenant_id": "uuid",
    "user_id": "uuid",
    "details": {
        "key_name": "production-key",
        "key_prefix": "sk-abc123"
    }
}
```

## 10. Security Headers

Response headers include:
- `X-Request-ID`: Unique request identifier
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Cache-Control: no-store` (for sensitive responses)

## 11. Environment Variables

Required security-related environment variables:

| Variable | Description |
|----------|-------------|
| `GATEWAY_SECRET_ENCRYPTION_KEY` | Fernet key for credential encryption |
| `GATEWAY_SSRF_BLOCKLIST_CIDRS` | Additional CIDRs to block |
| `GATEWAY_LOG_PAYLOAD_DEFAULT_MODE` | Default logging mode |
| `GATEWAY_REDIS_URL` | Redis URL for rate limiting |

## 12. Security Testing

### Automated Tests

- SSRF bypass attempts (redirect, DNS rebinding, IPv6)
- Header injection
- Authentication bypass
- Rate limit bypass
- Log redaction verification

### Manual Review Checklist

- [ ] Credential encryption working
- [ ] SSRF protection blocks metadata endpoints
- [ ] Rate limiting enforced
- [ ] Logs don't contain secrets
- [ ] TLS certificates valid
- [ ] Circuit breaker functioning
