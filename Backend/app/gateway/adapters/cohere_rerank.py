"""
Cohere Rerank Adapter.

This adapter handles communication with Cohere's Rerank API.
It translates between OpenAI-style rerank requests and Cohere's native format.

Cohere Rerank API: https://docs.cohere.com/reference/rerank
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


class CohereRerankAdapter(AdapterBase):
    """
    Adapter for Cohere Rerank API.

    Translates OpenAI-style rerank requests:
    {
        "model": "rerank-english-v3.0",
        "query": "What is the capital of France?",
        "documents": ["Paris is the capital of France.", "Berlin is in Germany."],
        "top_n": 3
    }

    To Cohere format:
    {
        "model": "rerank-english-v3.0",
        "query": "What is the capital of France?",
        "documents": ["Paris is the capital of France.", "Berlin is in Germany."],
        "top_n": 3,
        "return_documents": true
    }
    """

    ADAPTER_TYPE = "cohere"

    SUPPORTED_CAPABILITIES: Set[str] = {
        "rerank",
        "embeddings",
    }

    COHERE_RERANK_URL = "/v1/rerank"
    COHERE_EMBED_URL = "/v1/embed"

    async def build_upstream_request(
        self,
        openai_request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """Build request for Cohere API."""

        # Determine endpoint
        if "rerank" in route_ctx.endpoint:
            return await self._build_rerank_request(openai_request, route_ctx)
        elif "embedding" in route_ctx.endpoint:
            return await self._build_embed_request(openai_request, route_ctx)
        else:
            raise AdapterError(
                message=f"Unsupported endpoint for Cohere: {route_ctx.endpoint}",
                error_type="invalid_request_error",
                status_code=400
            )

    async def _build_rerank_request(
        self,
        openai_request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """Build Cohere rerank request."""

        base_url = route_ctx.upstream_base_url.rstrip("/")
        url = f"{base_url}{self.COHERE_RERANK_URL}"

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Cohere uses Bearer auth
        if route_ctx.upstream_credentials:
            headers["Authorization"] = f"Bearer {route_ctx.upstream_credentials}"

        headers.update(route_ctx.inject_headers)

        # Transform request body
        body = {
            "query": openai_request.get("query"),
            "documents": openai_request.get("documents", []),
            "return_documents": True,
        }

        # Optional parameters
        if "top_n" in openai_request:
            body["top_n"] = openai_request["top_n"]

        if "max_chunks_per_doc" in openai_request:
            body["max_chunks_per_doc"] = openai_request["max_chunks_per_doc"]

        # Model mapping
        if route_ctx.model_override:
            body["model"] = route_ctx.model_override
        elif route_ctx.upstream_model:
            body["model"] = route_ctx.upstream_model
        elif "model" in openai_request:
            body["model"] = openai_request["model"]

        return UpstreamRequest(
            method="POST",
            url=url,
            headers=headers,
            body=body,
            stream=False
        )

    async def _build_embed_request(
        self,
        openai_request: Dict[str, Any],
        route_ctx: RouteContext
    ) -> UpstreamRequest:
        """Build Cohere embed request."""

        base_url = route_ctx.upstream_base_url.rstrip("/")
        url = f"{base_url}{self.COHERE_EMBED_URL}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if route_ctx.upstream_credentials:
            headers["Authorization"] = f"Bearer {route_ctx.upstream_credentials}"

        headers.update(route_ctx.inject_headers)

        # Transform OpenAI format to Cohere format
        # OpenAI: {"input": ["text1", "text2"], "model": "..."}
        # Cohere: {"texts": ["text1", "text2"], "model": "..."}

        input_data = openai_request.get("input", [])
        if isinstance(input_data, str):
            input_data = [input_data]

        body = {
            "texts": input_data,
            "input_type": openai_request.get("input_type", "search_document"),
        }

        # Model mapping
        if route_ctx.model_override:
            body["model"] = route_ctx.model_override
        elif route_ctx.upstream_model:
            body["model"] = route_ctx.upstream_model
        elif "model" in openai_request:
            body["model"] = openai_request["model"]

        return UpstreamRequest(
            method="POST",
            url=url,
            headers=headers,
            body=body,
            stream=False
        )

    async def parse_upstream_response(
        self,
        upstream_response: httpx.Response,
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """Parse Cohere API response."""

        if upstream_response.status_code >= 400:
            try:
                error_body = upstream_response.json()
            except Exception:
                error_body = {"message": upstream_response.text}

            raise AdapterError(
                message=error_body.get("message", "Unknown error"),
                error_type="api_error",
                status_code=upstream_response.status_code,
                upstream_response=upstream_response
            )

        try:
            response_body = upstream_response.json()
        except Exception as e:
            raise AdapterError(
                message=f"Failed to parse Cohere response: {e}",
                error_type="parse_error",
                status_code=502
            )

        # Transform based on endpoint
        if "rerank" in route_ctx.endpoint:
            return self._transform_rerank_response(response_body, route_ctx)
        elif "embedding" in route_ctx.endpoint:
            return self._transform_embed_response(response_body, route_ctx)
        else:
            return response_body

    def _transform_rerank_response(
        self,
        cohere_response: Dict[str, Any],
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """
        Transform Cohere rerank response to OpenAI-style format.

        Cohere format:
        {
            "results": [
                {"index": 0, "relevance_score": 0.98, "document": {"text": "..."}},
                {"index": 1, "relevance_score": 0.45, "document": {"text": "..."}}
            ]
        }

        OpenAI-style format:
        {
            "object": "list",
            "data": [
                {"index": 0, "relevance_score": 0.98, "document": "..."},
                {"index": 1, "relevance_score": 0.45, "document": "..."}
            ],
            "model": "rerank-english-v3.0",
            "usage": {"total_tokens": ...}
        }
        """
        results = cohere_response.get("results", [])

        data = []
        for result in results:
            item = {
                "index": result.get("index"),
                "relevance_score": result.get("relevance_score"),
            }
            # Include document text if available
            doc = result.get("document", {})
            if isinstance(doc, dict):
                item["document"] = doc.get("text", "")
            else:
                item["document"] = str(doc)
            data.append(item)

        return {
            "object": "list",
            "data": data,
            "model": route_ctx.virtual_model,
            "usage": {
                "total_tokens": cohere_response.get("meta", {}).get("billed_units", {}).get("search_units", 0)
            }
        }

    def _transform_embed_response(
        self,
        cohere_response: Dict[str, Any],
        route_ctx: RouteContext
    ) -> Dict[str, Any]:
        """
        Transform Cohere embed response to OpenAI format.

        Cohere format:
        {
            "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
            "texts": ["text1", "text2"]
        }

        OpenAI format:
        {
            "object": "list",
            "data": [
                {"object": "embedding", "index": 0, "embedding": [0.1, 0.2, ...]},
                {"object": "embedding", "index": 1, "embedding": [0.3, 0.4, ...]}
            ],
            "model": "...",
            "usage": {...}
        }
        """
        embeddings = cohere_response.get("embeddings", [])

        data = []
        for i, embedding in enumerate(embeddings):
            data.append({
                "object": "embedding",
                "index": i,
                "embedding": embedding
            })

        return {
            "object": "list",
            "data": data,
            "model": route_ctx.virtual_model,
            "usage": {
                "prompt_tokens": cohere_response.get("meta", {}).get("billed_units", {}).get("input_tokens", 0),
                "total_tokens": cohere_response.get("meta", {}).get("billed_units", {}).get("input_tokens", 0)
            }
        }

    async def stream_translate(
        self,
        upstream_stream: AsyncIterator[bytes],
        route_ctx: RouteContext
    ) -> AsyncIterator[str]:
        """Cohere rerank doesn't support streaming."""
        raise AdapterError(
            message="Streaming not supported for Cohere endpoints",
            error_type="invalid_request_error",
            status_code=400
        )
        # Required to make this a generator
        yield ""
