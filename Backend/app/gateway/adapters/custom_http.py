"""
Custom HTTP Adapter.

This adapter allows users to define custom request/response transformations
using safe template configurations. It's designed for integrating with
arbitrary HTTP APIs that don't fit the standard adapter patterns.

Security Note: This adapter uses a restricted template system to prevent
code injection. Only predefined variables and operations are allowed.
"""

import json
import re
from typing import Any, AsyncIterator, Dict, Set

import httpx

from app.gateway.adapters.base import (
    AdapterBase,
    AdapterError,
    RouteContext,
    UpstreamRequest,
)


class CustomHTTPAdapter(AdapterBase):
    """
    Custom HTTP adapter with template-based transformations.

    Configuration is provided via the upstream's model_mapping field
    with a special format:

    {
        "_config": {
            "method": "POST",
            "path_template": "/api/v1/generate",
            "request_template": {
                "prompt": "{{messages[-1].content}}",
                "max_tokens": "{{max_tokens|default:1000}}"
            },
            "response_mapping": {
                "choices[0].message.content": "$.output.text",
                "usage.total_tokens": "$.meta.tokens"
            },
            "headers": {
                "X-Custom-Header": "value"
            }
        }
    }
    """

    ADAPTER_TYPE = "custom_http"

    SUPPORTED_CAPABILITIES: Set[str] = {
        "chat_completions",
        "completions",
        "embeddings",
    }

    # Template variable pattern: {{variable}} or {{variable|filter:arg}}
    TEMPLATE_PATTERN = re.compile(r"\{\{([^}]+)\}\}")

    # Allowed filters
    ALLOWED_FILTERS = {
        "default": lambda v, arg: v if v is not None else arg,
        "json": lambda v, _: json.dumps(v),
        "first": lambda v, _: v[0] if v else None,
        "last": lambda v, _: v[-1] if v else None,
        "length": lambda v, _: len(v) if v else 0,
        "join": lambda v, arg: (arg or ",").join(str(x) for x in v) if v else "",
    }

    async def build_upstream_request(
        self,
        openai_request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """Build custom HTTP request based on template configuration."""

        # Get configuration from model_mapping._config
        config = self._get_config(route_ctx)

        # Build URL
        base_url = route_ctx.upstream_base_url.rstrip("/")
        path = self._render_template(
            config.get("path_template", "/"),
            openai_request,
            route_ctx
        )
        url = f"{base_url}{path}"

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Add authentication
        if route_ctx.upstream_auth_type == "bearer" and route_ctx.upstream_credentials:
            headers["Authorization"] = f"Bearer {route_ctx.upstream_credentials}"
        elif route_ctx.upstream_auth_type == "header" and route_ctx.upstream_credentials:
            try:
                header_name, header_value = route_ctx.upstream_credentials.split(":", 1)
                headers[header_name.strip()] = header_value.strip()
            except ValueError:
                pass

        # Add configured headers
        for key, value in config.get("headers", {}).items():
            headers[key] = self._render_template(value, openai_request, route_ctx)

        headers.update(route_ctx.inject_headers)

        # Build request body from template
        request_template = config.get("request_template", {})
        body = self._build_body_from_template(request_template, openai_request, route_ctx)

        method = config.get("method", "POST").upper()
        stream = openai_request.get("stream", False) and config.get("supports_stream", False)

        return UpstreamRequest(
            method=method,
            url=url,
            headers=headers,
            body=body,
            stream=stream
        )

    def _get_config(self, route_ctx: RouteContext) -> Dict[str, Any]:
        """Extract configuration from route context."""
        # Configuration should be in extra or from upstream model_mapping
        config = route_ctx.extra.get("custom_http_config", {})
        if not config:
            raise AdapterError(
                message="Custom HTTP adapter requires _config in model_mapping",
                error_type="configuration_error",
                status_code=500
            )
        return config

    def _render_template(
        self,
        template: str,
        request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> str:
        """
        Render a template string with variables.

        Supports:
        - {{variable}} - Simple variable access
        - {{object.field}} - Nested access
        - {{array[0]}} - Array indexing
        - {{variable|filter:arg}} - Filters

        Variables available:
        - All fields from the OpenAI request
        - request_id, trace_id, virtual_model from route_ctx
        """
        if not isinstance(template, str):
            return str(template)

        context = {
            **request,
            "request_id": route_ctx.request_id,
            "trace_id": route_ctx.trace_id,
            "virtual_model": route_ctx.virtual_model,
            "upstream_model": route_ctx.upstream_model,
        }

        def replace_var(match):
            expr = match.group(1).strip()

            # Check for filter
            filter_name = None
            filter_arg = None
            if "|" in expr:
                expr, filter_part = expr.split("|", 1)
                expr = expr.strip()
                if ":" in filter_part:
                    filter_name, filter_arg = filter_part.split(":", 1)
                    filter_name = filter_name.strip()
                    filter_arg = filter_arg.strip()
                else:
                    filter_name = filter_part.strip()

            # Resolve variable
            value = self._resolve_path(expr, context)

            # Apply filter
            if filter_name and filter_name in self.ALLOWED_FILTERS:
                value = self.ALLOWED_FILTERS[filter_name](value, filter_arg)

            if value is None:
                return ""
            return str(value)

        return self.TEMPLATE_PATTERN.sub(replace_var, template)

    def _resolve_path(self, path: str, context: Dict[str, Any]) -> Any:
        """Resolve a dotted/bracketed path to a value."""
        # Parse path like "messages[-1].content" or "choices[0].message"
        parts = re.split(r"\.|\[", path)
        value = context

        for part in parts:
            if not part:
                continue

            # Handle array index
            if part.endswith("]"):
                part = part[:-1]
                try:
                    index = int(part)
                    if isinstance(value, (list, tuple)) and -len(value) <= index < len(value):
                        value = value[index]
                    else:
                        return None
                except ValueError:
                    return None
            else:
                # Handle dict key
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return None

        return value

    def _build_body_from_template(
        self,
        template: Dict[str, Any],
        request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """Build request body by rendering template recursively."""
        result = {}

        for key, value in template.items():
            if isinstance(value, str):
                rendered = self._render_template(value, request, route_ctx)
                # Try to parse as JSON if it looks like JSON
                if rendered.startswith(("{", "[", '"')) or rendered in ("true", "false", "null"):
                    try:
                        result[key] = json.loads(rendered)
                    except json.JSONDecodeError:
                        result[key] = rendered
                elif rendered.isdigit():
                    result[key] = int(rendered)
                else:
                    try:
                        result[key] = float(rendered)
                    except ValueError:
                        result[key] = rendered
            elif isinstance(value, dict):
                result[key] = self._build_body_from_template(value, request, route_ctx)
            elif isinstance(value, list):
                result[key] = [
                    self._build_body_from_template({"_": item}, request, route_ctx).get("_", item)
                    if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value

        return result

    async def parse_upstream_response(
        self,
        upstream_response: httpx.Response,
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """Parse upstream response using response mapping."""

        if upstream_response.status_code >= 400:
            try:
                error_body = upstream_response.json()
            except Exception:
                error_body = {"error": upstream_response.text}

            raise AdapterError(
                message=str(error_body.get("error", "Unknown error")),
                error_type="api_error",
                status_code=upstream_response.status_code,
                upstream_response=upstream_response
            )

        try:
            response_body = upstream_response.json()
        except Exception as e:
            raise AdapterError(
                message=f"Failed to parse response: {e}",
                error_type="parse_error",
                status_code=502
            )

        config = self._get_config(route_ctx)
        response_mapping = config.get("response_mapping", {})

        if not response_mapping:
            # No mapping configured, return as-is
            return response_body

        # Apply response mapping
        return self._apply_response_mapping(response_body, response_mapping, route_ctx)

    def _apply_response_mapping(
        self,
        response: Dict[str, Any],
        mapping: Dict[str, str],
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """
        Apply response mapping to transform upstream response to OpenAI format.

        Mapping format:
        {
            "target.path": "$.source.path"
        }

        The $ prefix indicates JSONPath-like access to the source response.
        """
        import time

        # Start with base OpenAI structure
        result = {
            "id": f"chatcmpl-{route_ctx.request_id[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": route_ctx.virtual_model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }

        for target_path, source_path in mapping.items():
            # Resolve source value
            if source_path.startswith("$."):
                source_value = self._resolve_path(source_path[2:], response)
            else:
                source_value = source_path

            # Set target value
            self._set_path(result, target_path, source_value)

        return result

    def _set_path(self, obj: Dict[str, Any], path: str, value: Any) -> None:
        """Set a value at a dotted/bracketed path."""
        parts = path.split(".")
        current = obj

        for i, part in enumerate(parts[:-1]):
            # Handle array index
            if "[" in part:
                key, index_str = part.split("[")
                index = int(index_str.rstrip("]"))

                if key not in current:
                    current[key] = []
                while len(current[key]) <= index:
                    current[key].append({})
                current = current[key][index]
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]

        # Set final value
        final_part = parts[-1]
        if "[" in final_part:
            key, index_str = final_part.split("[")
            index = int(index_str.rstrip("]"))
            if key not in current:
                current[key] = []
            while len(current[key]) <= index:
                current[key].append(None)
            current[key][index] = value
        else:
            current[final_part] = value

    async def stream_translate(
        self,
        upstream_stream: AsyncIterator[bytes],
        route_ctx: RouteContext
    ) -> AsyncIterator[str]:
        """
        Stream translation for custom HTTP.

        This is a basic implementation that assumes the upstream
        sends line-delimited JSON.
        """
        buffer = b""

        async for chunk in upstream_stream:
            buffer += chunk

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
                    yield data
                elif line_str.startswith("{"):
                    yield line_str
