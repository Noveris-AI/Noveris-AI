"""
OpenAI Adapter - Passthrough adapter for official OpenAI API.

This adapter handles direct communication with the official OpenAI API.
Since the gateway uses OpenAI-compatible format, this adapter is mostly
a passthrough with minimal transformation.
"""

import json
from typing import Any, AsyncIterator, Dict, Set

import httpx

from app.gateway.adapters.base import (
    AdapterBase,
    AdapterError,
    RouteContext,
    UpstreamRequest,
)


class OpenAIAdapter(AdapterBase):
    """
    Adapter for official OpenAI API.

    This is a passthrough adapter since our API surface matches OpenAI's.
    Main responsibilities:
    - Add authentication headers
    - Handle model mapping
    - Parse responses for usage tracking
    """

    ADAPTER_TYPE = "openai"

    SUPPORTED_CAPABILITIES: Set[str] = {
        "chat_completions",
        "completions",
        "responses",
        "embeddings",
        "images_generations",
        "images_edits",
        "images_variations",
        "audio_speech",
        "audio_transcriptions",
        "audio_translations",
        "moderations",
    }

    # Endpoint mapping
    ENDPOINT_PATHS = {
        "/v1/chat/completions": "/v1/chat/completions",
        "/v1/completions": "/v1/completions",
        "/v1/responses": "/v1/responses",
        "/v1/embeddings": "/v1/embeddings",
        "/v1/images/generations": "/v1/images/generations",
        "/v1/images/edits": "/v1/images/edits",
        "/v1/images/variations": "/v1/images/variations",
        "/v1/audio/speech": "/v1/audio/speech",
        "/v1/audio/transcriptions": "/v1/audio/transcriptions",
        "/v1/audio/translations": "/v1/audio/translations",
        "/v1/moderations": "/v1/moderations",
    }

    async def build_upstream_request(
        self,
        openai_request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """Build request for OpenAI API."""

        # Determine upstream path
        upstream_path = self.ENDPOINT_PATHS.get(route_ctx.endpoint)
        if not upstream_path:
            raise AdapterError(
                message=f"Unsupported endpoint: {route_ctx.endpoint}",
                error_type="invalid_request_error",
                status_code=400
            )

        # Build URL
        base_url = route_ctx.upstream_base_url.rstrip("/")
        url = f"{base_url}{upstream_path}"

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Add authentication
        if route_ctx.upstream_auth_type == "bearer" and route_ctx.upstream_credentials:
            headers["Authorization"] = f"Bearer {route_ctx.upstream_credentials}"

        # Add injected headers from route transform
        headers.update(route_ctx.inject_headers)

        # Add request tracking headers
        headers["X-Request-ID"] = route_ctx.request_id
        if route_ctx.trace_id:
            headers["X-Trace-ID"] = route_ctx.trace_id

        # Build request body
        body = openai_request.copy()

        # Apply model override if specified
        if route_ctx.model_override:
            body["model"] = route_ctx.model_override
        elif route_ctx.upstream_model and "model" in body:
            body["model"] = route_ctx.upstream_model

        # Check if streaming
        stream = body.get("stream", False)

        return UpstreamRequest(
            method="POST",
            url=url,
            headers=headers,
            body=body,
            stream=stream
        )

    async def parse_upstream_response(
        self,
        upstream_response: httpx.Response,
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """Parse OpenAI API response."""

        if upstream_response.status_code >= 400:
            # Parse error response
            try:
                error_body = upstream_response.json()
            except Exception:
                error_body = {"error": {"message": upstream_response.text}}

            raise AdapterError(
                message=error_body.get("error", {}).get("message", "Unknown error"),
                error_type=error_body.get("error", {}).get("type", "api_error"),
                status_code=upstream_response.status_code,
                code=error_body.get("error", {}).get("code"),
                upstream_response=upstream_response
            )

        # Parse successful response
        try:
            response_body = upstream_response.json()
        except Exception as e:
            raise AdapterError(
                message=f"Failed to parse upstream response: {e}",
                error_type="parse_error",
                status_code=502
            )

        return response_body

    async def stream_translate(
        self,
        upstream_stream: AsyncIterator[bytes],
        route_ctx: RouteContext
    ) -> AsyncIterator[str]:
        """
        Translate OpenAI SSE stream.

        OpenAI format is already compatible, so we just parse and forward.
        """
        buffer = b""

        async for chunk in upstream_stream:
            buffer += chunk

            # Process complete lines
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()

                if not line:
                    continue

                # Decode line
                try:
                    line_str = line.decode("utf-8")
                except UnicodeDecodeError:
                    continue

                # Check for SSE format
                if line_str.startswith("data: "):
                    data = line_str[6:]  # Remove "data: " prefix

                    if data == "[DONE]":
                        yield "[DONE]"
                        return

                    # Validate JSON
                    try:
                        json.loads(data)
                        yield data
                    except json.JSONDecodeError:
                        # Skip invalid JSON
                        continue
