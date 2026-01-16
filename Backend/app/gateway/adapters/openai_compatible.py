"""
OpenAI-Compatible Adapter for local deployments.

This adapter handles communication with OpenAI-compatible servers:
- vLLM
- sglang
- Xinference
- LMStudio
- Ollama (with OpenAI compatibility layer)

These servers implement OpenAI's API format but may have minor differences.
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


class OpenAICompatibleAdapter(AdapterBase):
    """
    Adapter for OpenAI-compatible servers.

    Handles vLLM, sglang, Xinference, and other compatible servers.
    Main differences from official OpenAI:
    - May not support all endpoints
    - May have different authentication
    - May have extra parameters
    """

    ADAPTER_TYPE = "openai_compatible"

    SUPPORTED_CAPABILITIES: Set[str] = {
        "chat_completions",
        "completions",
        "embeddings",
        # vLLM specific
        "audio_transcriptions",
        "audio_translations",
        # Extension
        "rerank",
    }

    # Endpoint mapping
    ENDPOINT_PATHS = {
        "/v1/chat/completions": "/v1/chat/completions",
        "/v1/completions": "/v1/completions",
        "/v1/embeddings": "/v1/embeddings",
        "/v1/audio/transcriptions": "/v1/audio/transcriptions",
        "/v1/audio/translations": "/v1/audio/translations",
        # vLLM/sglang specific endpoints
        "/v1/rerank": "/v1/rerank",
    }

    # Parameters that may need special handling
    VLLM_EXTRA_PARAMS = {
        "top_k",
        "min_p",
        "repetition_penalty",
        "length_penalty",
        "early_stopping",
        "ignore_eos",
        "skip_special_tokens",
        "spaces_between_special_tokens",
    }

    async def build_upstream_request(
        self,
        openai_request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """Build request for OpenAI-compatible server."""

        # Determine upstream path
        upstream_path = self.ENDPOINT_PATHS.get(route_ctx.endpoint)
        if not upstream_path:
            raise AdapterError(
                message=f"Unsupported endpoint for OpenAI-compatible server: {route_ctx.endpoint}",
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

        # Add authentication (many local servers don't require auth)
        if route_ctx.upstream_auth_type == "bearer" and route_ctx.upstream_credentials:
            headers["Authorization"] = f"Bearer {route_ctx.upstream_credentials}"
        elif route_ctx.upstream_auth_type == "header" and route_ctx.upstream_credentials:
            # Custom header format: "X-API-Key: value"
            try:
                header_name, header_value = route_ctx.upstream_credentials.split(":", 1)
                headers[header_name.strip()] = header_value.strip()
            except ValueError:
                pass

        # Add injected headers
        headers.update(route_ctx.inject_headers)

        # Add request tracking
        headers["X-Request-ID"] = route_ctx.request_id

        # Build request body
        body = openai_request.copy()

        # Apply model override
        if route_ctx.model_override:
            body["model"] = route_ctx.model_override
        elif route_ctx.upstream_model and "model" in body:
            body["model"] = route_ctx.upstream_model

        # Handle extra_body for vLLM-specific parameters
        extra_body = body.pop("extra_body", {})
        if extra_body:
            # Merge extra parameters into body
            for key in self.VLLM_EXTRA_PARAMS:
                if key in extra_body:
                    body[key] = extra_body[key]

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
        """Parse OpenAI-compatible server response."""

        if upstream_response.status_code >= 400:
            # Parse error response
            try:
                error_body = upstream_response.json()
            except Exception:
                error_body = {"error": {"message": upstream_response.text}}

            # Normalize error format
            error_info = error_body.get("error", {})
            if isinstance(error_info, str):
                error_info = {"message": error_info}

            raise AdapterError(
                message=error_info.get("message", "Unknown error"),
                error_type=error_info.get("type", "api_error"),
                status_code=upstream_response.status_code,
                code=error_info.get("code"),
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

        # Normalize response to OpenAI format
        response_body = self._normalize_response(response_body, route_ctx)

        return response_body

    def _normalize_response(
        self,
        response: Dict[str, Any],
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """Normalize response to match OpenAI format exactly."""

        # Ensure required fields exist
        if "object" not in response:
            # Infer object type from endpoint
            if "chat" in route_ctx.endpoint:
                response["object"] = "chat.completion"
            elif "embedding" in route_ctx.endpoint:
                response["object"] = "list"
            elif "completion" in route_ctx.endpoint:
                response["object"] = "text_completion"

        # Ensure model field
        if "model" not in response and route_ctx.virtual_model:
            response["model"] = route_ctx.virtual_model

        # Ensure usage exists for completion endpoints
        if "usage" not in response and "choices" in response:
            response["usage"] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }

        return response

    async def stream_translate(
        self,
        upstream_stream: AsyncIterator[bytes],
        route_ctx: RouteContext
    ) -> AsyncIterator[str]:
        """
        Translate SSE stream from OpenAI-compatible server.

        Most compatible servers use the same SSE format as OpenAI.
        We handle minor variations here.
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

                try:
                    line_str = line.decode("utf-8")
                except UnicodeDecodeError:
                    continue

                # Handle SSE format
                if line_str.startswith("data: "):
                    data = line_str[6:]

                    if data == "[DONE]":
                        yield "[DONE]"
                        return

                    # Validate and normalize JSON
                    try:
                        chunk_obj = json.loads(data)

                        # Ensure object type
                        if "object" not in chunk_obj:
                            chunk_obj["object"] = "chat.completion.chunk"

                        # Ensure model
                        if "model" not in chunk_obj:
                            chunk_obj["model"] = route_ctx.virtual_model

                        yield json.dumps(chunk_obj)
                    except json.JSONDecodeError:
                        continue

                # Handle alternative formats (some servers use different delimiters)
                elif line_str.startswith("{"):
                    try:
                        chunk_obj = json.loads(line_str)
                        if "object" not in chunk_obj:
                            chunk_obj["object"] = "chat.completion.chunk"
                        yield json.dumps(chunk_obj)
                    except json.JSONDecodeError:
                        continue
