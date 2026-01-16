"""
AI Gateway Adapter Base Class.

This module defines the base interface for upstream adapters.
Each adapter handles the translation between OpenAI-compatible
requests/responses and the upstream provider's native format.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Optional, Set
from uuid import UUID

import httpx


@dataclass
class RouteContext:
    """Context information for routing a request."""

    request_id: str
    trace_id: Optional[str]
    tenant_id: UUID
    api_key_id: UUID

    endpoint: str
    virtual_model: str
    upstream_id: UUID
    upstream_model: str

    # Upstream configuration
    upstream_base_url: str
    upstream_auth_type: str
    upstream_credentials: Optional[str]  # Decrypted credential

    # Request transform settings
    inject_headers: Dict[str, str] = field(default_factory=dict)
    model_override: Optional[str] = None
    timeout_ms: int = 120000

    # Extra metadata
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UpstreamRequest:
    """Request to send to upstream provider."""

    method: str
    url: str
    headers: Dict[str, str]
    body: Optional[Dict[str, Any]] = None
    content: Optional[bytes] = None  # For binary data (audio, images)
    stream: bool = False


@dataclass
class UpstreamResponse:
    """Response from upstream provider."""

    status_code: int
    headers: Dict[str, str]
    body: Optional[Dict[str, Any]] = None
    content: Optional[bytes] = None
    is_stream: bool = False

    # Extracted usage info
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    # Model info
    model: Optional[str] = None
    finish_reason: Optional[str] = None


class AdapterBase(ABC):
    """
    Base class for upstream adapters.

    An adapter handles the translation between OpenAI-compatible format
    and a specific upstream provider's format. Each adapter must implement:

    1. supports() - Check if adapter supports a capability
    2. build_upstream_request() - Transform OpenAI request to upstream format
    3. parse_upstream_response() - Transform upstream response to OpenAI format
    4. stream_translate() - Translate streaming SSE events

    Adapters should be stateless and thread-safe.
    """

    # Capabilities this adapter supports
    SUPPORTED_CAPABILITIES: Set[str] = set()

    # Adapter type identifier
    ADAPTER_TYPE: str = "base"

    def supports(self, capability: str) -> bool:
        """
        Check if this adapter supports the given capability.

        Args:
            capability: One of the Capability enum values

        Returns:
            True if the adapter can handle this capability
        """
        return capability in self.SUPPORTED_CAPABILITIES

    @abstractmethod
    async def build_upstream_request(
        self,
        openai_request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """
        Transform an OpenAI-format request to upstream format.

        Args:
            openai_request: The incoming request body in OpenAI format
            route_ctx: Routing context with upstream details

        Returns:
            UpstreamRequest ready to be sent

        Raises:
            AdapterError: If the request cannot be transformed
        """
        pass

    @abstractmethod
    async def parse_upstream_response(
        self,
        upstream_response: httpx.Response,
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """
        Transform an upstream response to OpenAI format.

        Args:
            upstream_response: The raw response from upstream
            route_ctx: Routing context

        Returns:
            Response body in OpenAI format

        Raises:
            AdapterError: If the response cannot be parsed
        """
        pass

    @abstractmethod
    async def stream_translate(
        self,
        upstream_stream: AsyncIterator[bytes],
        route_ctx: RouteContext
    ) -> AsyncIterator[str]:
        """
        Translate upstream SSE stream to OpenAI SSE format.

        Args:
            upstream_stream: Raw bytes stream from upstream
            route_ctx: Routing context

        Yields:
            SSE-formatted strings (without "data: " prefix)

        Raises:
            AdapterError: If stream cannot be translated
        """
        # This is an async generator, yield is required
        yield ""  # Placeholder to make this a generator

    def get_error_response(
        self,
        status_code: int,
        error_type: str,
        message: str,
        param: Optional[str] = None,
        code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate an OpenAI-style error response.

        Args:
            status_code: HTTP status code
            error_type: Error type (e.g., "invalid_request_error")
            message: Human-readable error message
            param: Optional parameter that caused the error
            code: Optional error code

        Returns:
            OpenAI-style error response dict
        """
        return {
            "error": {
                "message": message,
                "type": error_type,
                "param": param,
                "code": code or error_type,
            }
        }


class AdapterError(Exception):
    """Exception raised by adapters when processing fails."""

    def __init__(
        self,
        message: str,
        error_type: str = "adapter_error",
        status_code: int = 500,
        param: Optional[str] = None,
        code: Optional[str] = None,
        upstream_response: Optional[httpx.Response] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        self.param = param
        self.code = code
        self.upstream_response = upstream_response

    def to_openai_error(self) -> Dict[str, Any]:
        """Convert to OpenAI error format."""
        return {
            "error": {
                "message": self.message,
                "type": self.error_type,
                "param": self.param,
                "code": self.code or self.error_type,
            }
        }
