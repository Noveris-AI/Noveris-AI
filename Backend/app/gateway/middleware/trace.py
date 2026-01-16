"""
Request Tracing Middleware.

This module provides request ID generation and distributed tracing
support for the AI Gateway.

Features:
- Unique request ID generation
- Trace ID propagation
- OpenTelemetry integration (optional)
- Request context management
"""

import contextvars
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import UUID

# Context variables for request tracking
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id")
trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)
request_context_var: contextvars.ContextVar[Optional["RequestContext"]] = contextvars.ContextVar(
    "request_context", default=None
)


@dataclass
class RequestContext:
    """Context for a gateway request."""

    request_id: str
    trace_id: Optional[str]
    start_time: float
    tenant_id: Optional[UUID] = None
    api_key_id: Optional[UUID] = None
    endpoint: str = ""
    virtual_model: Optional[str] = None
    upstream_id: Optional[UUID] = None
    upstream_model: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


def generate_request_id() -> str:
    """
    Generate a unique request ID.

    Format: req_<timestamp_hex>_<random>
    Example: req_18d5b3f2_a7b9c4d2e1f0
    """
    timestamp = int(time.time() * 1000)
    random_part = secrets.token_hex(6)
    return f"req_{timestamp:x}_{random_part}"


def generate_trace_id() -> str:
    """
    Generate a trace ID compatible with W3C Trace Context.

    Format: 32 hex characters
    """
    return secrets.token_hex(16)


def get_request_id() -> str:
    """Get current request ID from context."""
    try:
        return request_id_var.get()
    except LookupError:
        return generate_request_id()


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context."""
    try:
        return trace_id_var.get()
    except LookupError:
        return None


def get_request_context() -> Optional[RequestContext]:
    """Get current request context."""
    try:
        return request_context_var.get()
    except LookupError:
        return None


def set_request_context(ctx: RequestContext) -> contextvars.Token:
    """Set request context for current async task."""
    request_id_var.set(ctx.request_id)
    if ctx.trace_id:
        trace_id_var.set(ctx.trace_id)
    return request_context_var.set(ctx)


class TracingMiddleware:
    """
    Middleware for request tracing.

    Handles:
    - Request ID generation or propagation
    - Trace ID propagation from incoming headers
    - Context setup for async request handling
    """

    # Standard headers for request/trace IDs
    REQUEST_ID_HEADER = "X-Request-ID"
    TRACE_ID_HEADER = "X-Trace-ID"
    TRACEPARENT_HEADER = "traceparent"  # W3C Trace Context

    def __init__(self, otel_enabled: bool = False):
        self.otel_enabled = otel_enabled
        self._tracer = None

        if otel_enabled:
            self._init_otel()

    def _init_otel(self) -> None:
        """Initialize OpenTelemetry tracer."""
        try:
            from opentelemetry import trace
            self._tracer = trace.get_tracer("gateway")
        except ImportError:
            self._tracer = None

    def extract_or_generate_ids(
        self,
        headers: Dict[str, str]
    ) -> tuple[str, Optional[str]]:
        """
        Extract request/trace IDs from headers or generate new ones.

        Args:
            headers: Request headers

        Returns:
            Tuple of (request_id, trace_id)
        """
        # Get or generate request ID
        request_id = headers.get(self.REQUEST_ID_HEADER)
        if not request_id:
            request_id = generate_request_id()

        # Get or generate trace ID
        trace_id = headers.get(self.TRACE_ID_HEADER)

        # Try W3C Trace Context format
        if not trace_id:
            traceparent = headers.get(self.TRACEPARENT_HEADER)
            if traceparent:
                trace_id = self._parse_traceparent(traceparent)

        if not trace_id:
            trace_id = generate_trace_id()

        return request_id, trace_id

    def _parse_traceparent(self, traceparent: str) -> Optional[str]:
        """
        Parse W3C Trace Context traceparent header.

        Format: version-trace_id-parent_id-flags
        Example: 00-0af7651916cd43dd8448eb211c80319c-b9c7c989f97918e1-01
        """
        try:
            parts = traceparent.split("-")
            if len(parts) >= 2:
                return parts[1]
        except Exception:
            pass
        return None

    def create_context(
        self,
        request_id: str,
        trace_id: Optional[str],
        endpoint: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> RequestContext:
        """Create a new request context."""
        ctx = RequestContext(
            request_id=request_id,
            trace_id=trace_id,
            start_time=time.time(),
            endpoint=endpoint,
            client_ip=client_ip,
            user_agent=user_agent
        )
        set_request_context(ctx)
        return ctx

    def get_response_headers(self) -> Dict[str, str]:
        """Get headers to include in response."""
        ctx = get_request_context()
        headers = {}

        if ctx:
            headers[self.REQUEST_ID_HEADER] = ctx.request_id
            if ctx.trace_id:
                headers[self.TRACE_ID_HEADER] = ctx.trace_id

        return headers


class RequestTimer:
    """Timer for measuring request duration."""

    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.first_token_time: Optional[float] = None

    def start(self) -> None:
        """Start the timer."""
        self.start_time = time.time()

    def stop(self) -> None:
        """Stop the timer."""
        self.end_time = time.time()

    def record_first_token(self) -> None:
        """Record time to first token (for streaming)."""
        if self.first_token_time is None:
            self.first_token_time = time.time()

    @property
    def total_ms(self) -> Optional[int]:
        """Get total duration in milliseconds."""
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return int((end - self.start_time) * 1000)

    @property
    def ttft_ms(self) -> Optional[int]:
        """Get time to first token in milliseconds."""
        if self.start_time is None or self.first_token_time is None:
            return None
        return int((self.first_token_time - self.start_time) * 1000)
