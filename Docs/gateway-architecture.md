# AI Gateway Architecture Document

## 1. Overview

The AI Gateway module provides a unified OpenAI-compatible API layer for routing requests to multiple upstream LLM/AI services. It supports:

- **LLM Chat/Completions** (OpenAI, Anthropic, local deployments)
- **Embeddings** (OpenAI, Cohere, local models)
- **Rerank** (Cohere, Jina, local models)
- **Image Generation** (DALL-E, Stable Diffusion)
- **Audio** (Speech-to-Text, Text-to-Speech)
- **Moderations**

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CONTROL PLANE                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Upstreams  │  │   Virtual   │  │   Routes/   │  │  API Keys   │        │
│  │    CRUD     │  │   Models    │  │  Policies   │  │    CRUD     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    Request Logs & Analytics                      │       │
│  └─────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Config Hot-Reload
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               DATA PLANE                                    │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                         MIDDLEWARE CHAIN                            │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐     │    │
│  │  │  Auth   │→│  Rate   │→│  SSRF   │→│ Trace   │→│ Request  │     │    │
│  │  │ (Bearer)│ │  Limit  │ │  Guard  │ │   ID    │ │ Logging  │     │    │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────────┘     │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                        ROUTING ENGINE                               │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    │
│  │  │    Policy    │  │   Upstream   │  │    Fallback/Retry        │  │    │
│  │  │   Matcher    │→ │   Selector   │→ │      Controller          │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                        ADAPTER LAYER                                │    │
│  │  ┌─────────┐ ┌───────────────┐ ┌────────┐ ┌──────┐ ┌────────────┐ │    │
│  │  │ OpenAI  │ │ OpenAI-Compat │ │ Cohere │ │  SD  │ │ CustomHTTP │ │    │
│  │  │ Adapter │ │   Adapter     │ │Adapter │ │Adapt.│ │  Adapter   │ │    │
│  │  └─────────┘ └───────────────┘ └────────┘ └──────┘ └────────────┘ │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                     HTTP CLIENT (httpx AsyncClient)                 │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    │
│  │  │  Connection  │  │    SSRF      │  │     Timeout/Retry        │  │    │
│  │  │     Pool     │  │  Validator   │  │      Handler             │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           UPSTREAM PROVIDERS                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ OpenAI  │ │Anthropic│ │  vLLM   │ │ sglang  │ │Xinference│ │  Cohere │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 3. API Surface (OpenAI-Compatible)

### 3.1 Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completions (streaming supported) |
| `/v1/completions` | POST | Legacy text completions |
| `/v1/responses` | POST | OpenAI Responses API |
| `/v1/embeddings` | POST | Vector embeddings |
| `/v1/images/generations` | POST | Image generation |
| `/v1/images/edits` | POST | Image editing |
| `/v1/images/variations` | POST | Image variations |
| `/v1/audio/speech` | POST | Text-to-speech |
| `/v1/audio/transcriptions` | POST | Speech-to-text |
| `/v1/audio/translations` | POST | Audio translation |
| `/v1/moderations` | POST | Content moderation |
| `/v1/models` | GET | List available models |

### 3.2 Extension Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/rerank` | POST | Document reranking (Cohere-style) |

### 3.3 Request/Response Format

All endpoints follow OpenAI API format. Example for chat completions:

**Request:**
```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "stream": true
}
```

**Response (non-streaming):**
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-4o",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "Hello! How can I help?"},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 9, "completion_tokens": 12, "total_tokens": 21}
}
```

**Response (streaming SSE):**
```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1677652288,"model":"gpt-4o","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1677652288,"model":"gpt-4o","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1677652288,"model":"gpt-4o","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### 3.4 Error Format

```json
{
  "error": {
    "message": "Invalid API key provided",
    "type": "invalid_request_error",
    "param": null,
    "code": "invalid_api_key"
  }
}
```

## 4. Core Abstractions

### 4.1 VirtualModel

A VirtualModel is the externally exposed model identifier that clients use.

```python
class VirtualModel:
    id: UUID
    name: str              # e.g., "openai/gpt-4o", "local/llama3-70b"
    capabilities: set[str] # chat_completions, embeddings, images, etc.
    tags: dict[str, str]   # metadata for filtering
    default_route_id: UUID # fallback route
```

**Capability Types:**
- `chat_completions` - Chat/conversation models
- `completions` - Legacy text completion
- `responses` - OpenAI Responses API
- `embeddings` - Vector embeddings
- `images_generations` - Image generation
- `images_edits` - Image editing
- `images_variations` - Image variations
- `audio_speech` - Text-to-speech
- `audio_transcriptions` - Speech-to-text
- `audio_translations` - Audio translation
- `moderations` - Content moderation
- `rerank` - Document reranking

### 4.2 Upstream

An Upstream represents a backend AI service provider.

```python
class Upstream:
    id: UUID
    name: str
    type: UpstreamType     # openai, openai_compatible, anthropic, cohere, etc.
    base_url: str
    auth_type: AuthType    # bearer, header, query, none
    credentials_ref: UUID  # encrypted secret reference

    # Security
    allow_hosts: list[str]    # hostname whitelist
    allow_cidrs: list[str]    # CIDR whitelist

    # Capabilities
    supported_capabilities: set[str]
    model_mapping: dict[str, str]  # virtual_model -> upstream_model

    # Reliability
    timeout_ms: int
    max_retries: int
    circuit_breaker: CircuitBreakerConfig
    healthcheck: HealthCheckConfig

    enabled: bool
```

**Upstream Types:**
- `openai` - Official OpenAI API
- `openai_compatible` - vLLM, sglang, Xinference, etc.
- `anthropic` - Anthropic Claude
- `gemini` - Google Gemini
- `cohere` - Cohere (embeddings, rerank)
- `stable_diffusion` - Stable Diffusion WebUI/API
- `custom_http` - Generic HTTP adapter with templates

### 4.3 RoutingPolicy

Defines how requests are matched and routed to upstreams.

```python
class RoutingPolicy:
    id: UUID
    name: str
    priority: int          # Lower = higher priority

    # Match conditions (AND logic)
    match: MatchConfig
        endpoint: str      # e.g., "/v1/chat/completions"
        virtual_model: str # pattern with wildcards: "openai/*"
        tenant_id: UUID    # optional
        api_key_id: UUID   # optional
        tags: dict         # optional

    # Routing action
    action: ActionConfig
        primary_upstreams: list[WeightedUpstream]
        fallback_upstreams: list[UUID]  # ordered fallback chain
        retry_policy: RetryPolicy
        cache_policy: CachePolicy       # for embeddings/rerank
        request_transform: TransformConfig

    enabled: bool
```

### 4.4 APIKey

External API keys for gateway access.

```python
class APIKey:
    id: UUID
    key_hash: str          # bcrypt hash (only prefix shown)
    tenant_id: UUID
    name: str

    # Access control
    allowed_models: list[str]    # patterns
    allowed_endpoints: list[str]

    # Rate limiting
    rate_limit: RateLimitConfig
        requests_per_minute: int
        tokens_per_minute: int
        tokens_per_day: int

    # Quota
    quota: QuotaConfig
        max_tokens: int
        max_requests: int
        reset_interval: str  # daily, monthly

    # Logging
    log_payload_mode: LogPayloadMode  # none, metadata_only, sampled, full

    enabled: bool
```

## 5. Adapter Design

### 5.1 Base Interface

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class AdapterBase(ABC):
    """Base class for upstream adapters."""

    @abstractmethod
    def supports(self, capability: str) -> bool:
        """Check if adapter supports the capability."""
        pass

    @abstractmethod
    async def build_upstream_request(
        self,
        openai_request: dict,
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """Transform OpenAI request to upstream format."""
        pass

    @abstractmethod
    async def parse_upstream_response(
        self,
        upstream_response: httpx.Response,
        route_ctx: RouteContext
    ) -> dict:
        """Transform upstream response to OpenAI format."""
        pass

    @abstractmethod
    async def stream_translate(
        self,
        upstream_stream: AsyncIterator[bytes],
        route_ctx: RouteContext
    ) -> AsyncIterator[str]:
        """Translate upstream SSE stream to OpenAI format."""
        pass
```

### 5.2 Implemented Adapters

| Adapter | Type | Capabilities | Notes |
|---------|------|--------------|-------|
| `OpenAIAdapter` | Passthrough | All | Direct proxy to OpenAI |
| `OpenAICompatibleAdapter` | Transform | chat, embeddings, completions | vLLM, sglang, Xinference |
| `AnthropicAdapter` | Transform | chat | Claude API format conversion |
| `CohereRerankAdapter` | Transform | rerank | Cohere rerank API |
| `StableDiffusionAdapter` | Transform | images | SD WebUI/A1111 API |
| `CustomHTTPAdapter` | Template | Any | User-defined templates |

### 5.3 Adapter Selection Flow

```
1. Incoming request → determine endpoint type
2. Extract model from request → resolve virtual model
3. Get upstream from route → get adapter by upstream.type
4. Adapter.build_upstream_request() → transform request
5. Execute HTTP call with SSRF protection
6. Adapter.parse_upstream_response() → transform response
7. Return OpenAI-formatted response
```

## 6. Routing Engine

### 6.1 Policy Matching Algorithm

```python
def select_route(request: GatewayRequest) -> RoutingPolicy:
    """
    Match request to routing policy.
    Policies are sorted by priority (ascending).
    First match wins.
    """
    endpoint = request.path
    virtual_model = request.body.get("model")
    tenant_id = request.tenant_id
    api_key_id = request.api_key_id

    for policy in sorted_policies:
        if not policy.enabled:
            continue

        match = policy.match

        # All specified conditions must match (AND)
        if match.endpoint and not fnmatch(endpoint, match.endpoint):
            continue
        if match.virtual_model and not fnmatch(virtual_model, match.virtual_model):
            continue
        if match.tenant_id and match.tenant_id != tenant_id:
            continue
        if match.api_key_id and match.api_key_id != api_key_id:
            continue
        if match.tags and not tags_match(match.tags, request.tags):
            continue

        return policy

    raise NoRouteFoundError(f"No route for {endpoint} model={virtual_model}")
```

### 6.2 Upstream Selection

```python
def select_upstream(policy: RoutingPolicy) -> Upstream:
    """
    Select upstream from policy action.
    Supports weighted random selection.
    """
    primaries = policy.action.primary_upstreams

    # Filter healthy upstreams
    healthy = [u for u in primaries if circuit_breaker.is_healthy(u.upstream_id)]

    if not healthy:
        # Try fallbacks
        for fallback_id in policy.action.fallback_upstreams:
            if circuit_breaker.is_healthy(fallback_id):
                return get_upstream(fallback_id)
        raise AllUpstreamsUnhealthyError()

    # Weighted random selection
    total_weight = sum(u.weight for u in healthy)
    r = random.uniform(0, total_weight)
    current = 0
    for u in healthy:
        current += u.weight
        if r <= current:
            return get_upstream(u.upstream_id)
```

### 6.3 Retry and Fallback

```python
async def execute_with_retry(
    request: UpstreamRequest,
    policy: RoutingPolicy
) -> UpstreamResponse:
    """Execute request with retry and fallback logic."""

    retry_policy = policy.action.retry_policy
    upstreams = get_ordered_upstreams(policy)

    last_error = None
    for upstream in upstreams:
        for attempt in range(retry_policy.max_retries + 1):
            try:
                response = await http_client.send(request, upstream)

                if response.status_code < 500:
                    return response

                # 5xx: retry if idempotent
                if not retry_policy.retry_on_5xx:
                    raise UpstreamError(response)

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                await asyncio.sleep(retry_policy.backoff_ms * (2 ** attempt) / 1000)
                continue
            except Exception as e:
                last_error = e
                circuit_breaker.record_failure(upstream.id)
                break  # Try next upstream

        # Mark upstream as unhealthy after exhausting retries
        circuit_breaker.record_failure(upstream.id)

    raise AllUpstreamsFailedError(last_error)
```

## 7. Security

### 7.1 SSRF Protection

```python
class SSRFGuard:
    """Prevent Server-Side Request Forgery attacks."""

    BLOCKED_CIDRS = [
        "127.0.0.0/8",      # Loopback
        "10.0.0.0/8",       # Private
        "172.16.0.0/12",    # Private
        "192.168.0.0/16",   # Private
        "169.254.0.0/16",   # Link-local / AWS metadata
        "::1/128",          # IPv6 loopback
        "fc00::/7",         # IPv6 private
        "fe80::/10",        # IPv6 link-local
    ]

    def validate_url(self, url: str, upstream: Upstream) -> bool:
        """Validate URL against SSRF protections."""
        parsed = urlparse(url)

        # 1. Scheme must be http or https
        if parsed.scheme not in ("http", "https"):
            raise SSRFError(f"Invalid scheme: {parsed.scheme}")

        # 2. Resolve hostname to IP(s)
        ips = self._resolve_dns(parsed.hostname)

        # 3. Check against blocked CIDRs
        for ip in ips:
            if self._is_blocked(ip):
                raise SSRFError(f"Blocked IP: {ip}")

        # 4. Check against upstream allowlist
        if upstream.allow_hosts:
            if parsed.hostname not in upstream.allow_hosts:
                raise SSRFError(f"Host not in allowlist: {parsed.hostname}")

        if upstream.allow_cidrs:
            if not any(self._ip_in_cidr(ip, cidr) for ip in ips for cidr in upstream.allow_cidrs):
                raise SSRFError(f"IP not in allowed CIDRs")

        return True

    def validate_redirect(self, original_url: str, redirect_url: str) -> bool:
        """Validate redirect target (prevent redirect-based SSRF)."""
        # Must pass same validation as original
        return self.validate_url(redirect_url, ...)
```

### 7.2 Rate Limiting

```python
class RateLimiter:
    """Redis-based rate limiting."""

    async def check_rate_limit(
        self,
        api_key: APIKey,
        endpoint: str
    ) -> RateLimitResult:
        """Check and update rate limits."""

        # Per-minute request limit
        minute_key = f"rl:{api_key.id}:rpm:{current_minute()}"
        current = await redis.incr(minute_key)
        await redis.expire(minute_key, 60)

        if current > api_key.rate_limit.requests_per_minute:
            return RateLimitResult(
                allowed=False,
                retry_after=seconds_until_next_minute(),
                reason="rate_limit_exceeded"
            )

        # Check token limits similarly...

        return RateLimitResult(allowed=True)
```

### 7.3 Secret Encryption

```python
from cryptography.fernet import Fernet

class SecretManager:
    """Encrypted secret storage."""

    def __init__(self, encryption_key: str):
        self.fernet = Fernet(encryption_key.encode())

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a secret value."""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a secret value."""
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

## 8. Observability

### 8.1 Request Logging

Every gateway request is logged with:

```python
class GatewayRequestLog:
    request_id: str        # Unique request ID
    trace_id: str          # Distributed tracing ID
    tenant_id: UUID
    api_key_id: UUID

    # Request info
    endpoint: str
    virtual_model: str
    upstream_id: UUID
    upstream_model: str

    # Response info
    status_code: int
    error_type: str        # if error

    # Timing
    latency_ms: int        # Total latency
    upstream_latency_ms: int

    # Usage
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal

    # Metadata
    request_meta: dict     # Headers, client IP, etc.
    response_meta: dict    # Model, finish_reason, etc.

    created_at: datetime
```

### 8.2 Metrics (Prometheus)

```python
# Request metrics
gateway_requests_total = Counter(
    "gateway_requests_total",
    "Total gateway requests",
    ["endpoint", "virtual_model", "upstream", "status"]
)

gateway_request_duration_seconds = Histogram(
    "gateway_request_duration_seconds",
    "Request latency",
    ["endpoint", "virtual_model", "upstream"]
)

gateway_tokens_total = Counter(
    "gateway_tokens_total",
    "Total tokens processed",
    ["virtual_model", "upstream", "token_type"]  # prompt/completion
)

# Upstream health
gateway_upstream_health = Gauge(
    "gateway_upstream_health",
    "Upstream health status (1=healthy, 0=unhealthy)",
    ["upstream_id", "upstream_name"]
)

gateway_circuit_breaker_state = Gauge(
    "gateway_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["upstream_id"]
)
```

### 8.3 OpenTelemetry Integration

```python
from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("gateway")

async def handle_request(request):
    with tracer.start_as_current_span(
        "gateway.request",
        kind=SpanKind.SERVER,
        attributes={
            "gateway.endpoint": request.path,
            "gateway.model": request.body.get("model"),
            "gateway.api_key_id": str(request.api_key_id),
        }
    ) as span:
        # ... process request

        with tracer.start_as_current_span(
            "gateway.upstream_call",
            kind=SpanKind.CLIENT,
            attributes={
                "upstream.id": str(upstream.id),
                "upstream.url": upstream.base_url,
            }
        ):
            response = await call_upstream(...)

        span.set_attribute("gateway.status_code", response.status_code)
        span.set_attribute("gateway.tokens", usage.total_tokens)
```

## 9. Configuration

### 9.1 Environment Variables

```bash
# Gateway Service
GATEWAY_PUBLIC_BASE_URL=https://api.example.com
GATEWAY_BIND_HOST=0.0.0.0
GATEWAY_BIND_PORT=8080

# Request Limits
GATEWAY_REQUEST_MAX_BYTES=10485760  # 10MB
GATEWAY_TIMEOUT_MS_DEFAULT=120000   # 2 minutes
GATEWAY_STREAMING_TIMEOUT_MS=600000 # 10 minutes

# HTTP Client Pool
GATEWAY_HTTP_POOL_MAX_CONNECTIONS=100
GATEWAY_HTTP_POOL_MAX_KEEPALIVE=20
GATEWAY_HTTP_POOL_KEEPALIVE_EXPIRY=30

# Database
GATEWAY_DB_URL=postgresql+asyncpg://user:pass@localhost/db

# Redis
GATEWAY_REDIS_URL=redis://:password@localhost:6379/0

# Security
GATEWAY_SECRET_ENCRYPTION_KEY=<32-byte-base64-key>
GATEWAY_SSRF_BLOCKLIST_CIDRS=169.254.0.0/16,127.0.0.0/8

# Logging
GATEWAY_LOG_RETENTION_DAYS=30
GATEWAY_LOG_PAYLOAD_DEFAULT_MODE=metadata_only

# Observability
GATEWAY_PROMETHEUS_ENABLED=true
GATEWAY_OTEL_ENABLED=true
GATEWAY_OTEL_EXPORTER_ENDPOINT=http://jaeger:4317
```

## 10. Database Schema

See `Backend/alembic_migrations/versions/add_gateway_tables.py` for complete schema.

### 10.1 Tables Overview

| Table | Purpose |
|-------|---------|
| `gateway_upstreams` | Upstream provider configurations |
| `gateway_virtual_models` | Exposed model identifiers |
| `gateway_routes` | Routing policies |
| `gateway_api_keys` | External API keys |
| `gateway_requests` | Request logs |
| `gateway_secrets` | Encrypted credentials |

### 10.2 Key Relationships

```
gateway_api_keys ──┐
                   │
gateway_routes ────┼──▶ gateway_upstreams
                   │         │
gateway_virtual_models ──────┘
                   │
                   ▼
            gateway_requests
```

## 11. Frontend Pages

| Page | Purpose |
|------|---------|
| `/dashboard/gateway` | Overview dashboard |
| `/dashboard/gateway/upstreams` | Upstream management |
| `/dashboard/gateway/models` | Virtual model management |
| `/dashboard/gateway/routes` | Routing policy editor |
| `/dashboard/gateway/api-keys` | API key management |
| `/dashboard/gateway/logs` | Request log viewer |

## 12. Implementation Checklist

- [ ] Database migrations
- [ ] Core adapters (OpenAI, OpenAI-Compatible, Cohere, SD)
- [ ] Routing engine
- [ ] Middleware chain (auth, rate limit, SSRF, trace)
- [ ] Control plane APIs
- [ ] Frontend pages
- [ ] Metrics and logging
- [ ] Security tests
- [ ] Performance tests
