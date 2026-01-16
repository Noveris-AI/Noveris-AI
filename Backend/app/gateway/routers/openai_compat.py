"""
Gateway Data Plane Router.

This module implements the OpenAI-compatible API endpoints for the AI Gateway.
All endpoints follow OpenAI API specification and route requests to upstream providers.

Endpoints:
- POST /v1/chat/completions - Chat completions (streaming supported)
- POST /v1/completions - Legacy text completions
- POST /v1/embeddings - Vector embeddings
- POST /v1/images/generations - Image generation
- POST /v1/audio/speech - Text-to-speech
- POST /v1/audio/transcriptions - Speech-to-text
- POST /v1/rerank - Document reranking (extension)
- GET /v1/models - List available models
"""

import asyncio
import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.gateway.adapters import AdapterError, RouteContext, get_adapter
from app.gateway.middleware import (
    AuthContext,
    AuthenticationError,
    GatewayAuthenticator,
    RateLimiter,
    RateLimitConfig,
    QuotaManager,
    SSRFGuard,
    TracingMiddleware,
    RequestContext,
    RequestTimer,
    get_ssrf_guard,
    generate_request_id,
)
from app.gateway.routing import (
    RoutingEngine,
    RoutingContext,
    NoRouteFoundError,
    NoHealthyUpstreamError,
    get_circuit_breaker_registry,
)
from app.models.gateway import (
    GatewayUpstream,
    GatewayRoute,
    GatewayVirtualModel,
    GatewayRequest,
    GatewayAPIKey,
)


router = APIRouter(prefix="/v1", tags=["gateway"])


# =============================================================================
# Dependencies
# =============================================================================

async def get_auth_context(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> AuthContext:
    """Authenticate request and return auth context."""
    authenticator = GatewayAuthenticator(db)
    endpoint = request.url.path

    try:
        # Extract model from request body if available
        model = None
        if request.method == "POST":
            try:
                body = await request.json()
                model = body.get("model")
            except Exception:
                pass

        return await authenticator.authenticate(authorization, endpoint, model)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.to_openai_error()
        )


async def get_routing_engine(
    auth_ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db)
) -> RoutingEngine:
    """Build routing engine with current routes and upstreams."""
    tenant_id = auth_ctx.tenant_id

    # Fetch routes
    routes_stmt = select(GatewayRoute).where(
        GatewayRoute.tenant_id == tenant_id,
        GatewayRoute.enabled == True
    ).order_by(GatewayRoute.priority)
    routes_result = await db.execute(routes_stmt)
    routes = list(routes_result.scalars().all())

    # Fetch upstreams
    upstreams_stmt = select(GatewayUpstream).where(
        GatewayUpstream.tenant_id == tenant_id,
        GatewayUpstream.enabled == True
    )
    upstreams_result = await db.execute(upstreams_stmt)
    upstreams = {u.id: u for u in upstreams_result.scalars().all()}

    # Fetch virtual models
    models_stmt = select(GatewayVirtualModel).where(
        GatewayVirtualModel.tenant_id == tenant_id,
        GatewayVirtualModel.enabled == True
    )
    models_result = await db.execute(models_stmt)
    virtual_models = {m.name: m for m in models_result.scalars().all()}

    return RoutingEngine(
        routes=routes,
        upstreams=upstreams,
        virtual_models=virtual_models,
        circuit_breakers=get_circuit_breaker_registry()
    )


# =============================================================================
# Helper Functions
# =============================================================================

async def get_upstream_credentials(
    upstream: GatewayUpstream,
    db: AsyncSession
) -> Optional[str]:
    """Decrypt and return upstream credentials."""
    if not upstream.credentials_secret_id:
        return None

    from app.models.gateway import GatewaySecret
    from app.gateway.services.secret_manager import SecretManager

    stmt = select(GatewaySecret).where(GatewaySecret.id == upstream.credentials_secret_id)
    result = await db.execute(stmt)
    secret = result.scalar_one_or_none()

    if not secret:
        return None

    # Decrypt using secret manager
    secret_manager = SecretManager()
    return secret_manager.decrypt(secret.ciphertext)


def build_route_context(
    request_id: str,
    trace_id: Optional[str],
    auth_ctx: AuthContext,
    endpoint: str,
    virtual_model: str,
    upstream: GatewayUpstream,
    upstream_model: str,
    credentials: Optional[str],
    route: GatewayRoute
) -> RouteContext:
    """Build route context for adapter."""
    action = route.action or {}
    transform = action.get("request_transform", {})

    return RouteContext(
        request_id=request_id,
        trace_id=trace_id,
        tenant_id=auth_ctx.tenant_id,
        api_key_id=auth_ctx.api_key_id,
        endpoint=endpoint,
        virtual_model=virtual_model,
        upstream_id=upstream.id,
        upstream_model=upstream_model,
        upstream_base_url=upstream.base_url,
        upstream_auth_type=upstream.auth_type.value if upstream.auth_type else "bearer",
        upstream_credentials=credentials,
        inject_headers=transform.get("inject_headers", {}),
        model_override=transform.get("model_override"),
        timeout_ms=action.get("timeout_ms_override", upstream.timeout_ms or 120000)
    )


async def execute_upstream_request(
    route_ctx: RouteContext,
    request_body: Dict[str, Any],
    upstream: GatewayUpstream
) -> httpx.Response:
    """Execute request to upstream with SSRF protection."""
    adapter = get_adapter(upstream.type.value)

    # Build upstream request
    upstream_request = await adapter.build_upstream_request(request_body, route_ctx)

    # Validate URL against SSRF
    ssrf_guard = get_ssrf_guard()
    ssrf_guard.validate_url(
        upstream_request.url,
        allow_hosts=upstream.allow_hosts,
        allow_cidrs=upstream.allow_cidrs
    )

    # Execute request
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(route_ctx.timeout_ms / 1000)
    ) as client:
        response = await client.request(
            method=upstream_request.method,
            url=upstream_request.url,
            headers=upstream_request.headers,
            json=upstream_request.body if upstream_request.body else None,
            content=upstream_request.content if upstream_request.content else None
        )

    return response


async def stream_response(
    route_ctx: RouteContext,
    request_body: Dict[str, Any],
    upstream: GatewayUpstream,
    timer: RequestTimer
) -> AsyncIterator[str]:
    """Stream SSE response from upstream."""
    adapter = get_adapter(upstream.type.value)

    # Build upstream request
    upstream_request = await adapter.build_upstream_request(request_body, route_ctx)

    # Validate URL
    ssrf_guard = get_ssrf_guard()
    ssrf_guard.validate_url(
        upstream_request.url,
        allow_hosts=upstream.allow_hosts,
        allow_cidrs=upstream.allow_cidrs
    )

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(route_ctx.timeout_ms / 1000)
    ) as client:
        async with client.stream(
            method=upstream_request.method,
            url=upstream_request.url,
            headers=upstream_request.headers,
            json=upstream_request.body
        ) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                try:
                    error_json = json.loads(error_body)
                    error_msg = error_json.get("error", {}).get("message", "Unknown error")
                except Exception:
                    error_msg = error_body.decode()
                raise AdapterError(
                    message=error_msg,
                    status_code=response.status_code
                )

            first_chunk = True
            async for chunk in adapter.stream_translate(
                response.aiter_bytes(),
                route_ctx
            ):
                if first_chunk:
                    timer.record_first_token()
                    first_chunk = False

                if chunk == "[DONE]":
                    yield "data: [DONE]\n\n"
                else:
                    yield f"data: {chunk}\n\n"


async def log_request(
    db: AsyncSession,
    request_id: str,
    trace_id: Optional[str],
    auth_ctx: AuthContext,
    endpoint: str,
    virtual_model: Optional[str],
    upstream: Optional[GatewayUpstream],
    upstream_model: Optional[str],
    status_code: int,
    error_type: Optional[str],
    error_message: Optional[str],
    timer: RequestTimer,
    usage: Optional[Dict[str, int]] = None,
    request_meta: Optional[Dict[str, Any]] = None,
    response_meta: Optional[Dict[str, Any]] = None
) -> None:
    """Log request to database."""
    try:
        log_entry = GatewayRequest(
            request_id=request_id,
            trace_id=trace_id,
            tenant_id=auth_ctx.tenant_id,
            api_key_id=auth_ctx.api_key_id,
            endpoint=endpoint,
            method="POST",
            virtual_model=virtual_model,
            upstream_id=upstream.id if upstream else None,
            upstream_model=upstream_model,
            status_code=status_code,
            error_type=error_type,
            error_message=error_message,
            latency_ms=timer.total_ms,
            time_to_first_token_ms=timer.ttft_ms,
            prompt_tokens=usage.get("prompt_tokens") if usage else None,
            completion_tokens=usage.get("completion_tokens") if usage else None,
            total_tokens=usage.get("total_tokens") if usage else None,
            request_meta=request_meta or {},
            response_meta=response_meta or {}
        )
        db.add(log_entry)
        await db.commit()
    except Exception:
        # Don't fail request on logging error
        pass


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    auth_ctx: AuthContext = Depends(get_auth_context),
    routing_engine: RoutingEngine = Depends(get_routing_engine),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a chat completion.

    Compatible with OpenAI's /v1/chat/completions endpoint.
    Supports streaming via SSE when stream=true.
    """
    timer = RequestTimer()
    timer.start()

    request_id = generate_request_id()
    trace_id = request.headers.get("X-Trace-ID")
    endpoint = "/v1/chat/completions"

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={
            "error": {"message": "Invalid JSON body", "type": "invalid_request_error"}
        })

    model = body.get("model")
    if not model:
        raise HTTPException(status_code=400, detail={
            "error": {"message": "Missing 'model' field", "type": "invalid_request_error"}
        })

    stream = body.get("stream", False)

    try:
        # Route selection
        routing_ctx = RoutingContext(
            endpoint=endpoint,
            virtual_model=model,
            tenant_id=auth_ctx.tenant_id,
            api_key_id=auth_ctx.api_key_id
        )
        selected = routing_engine.select_route(routing_ctx)

        # Get credentials
        credentials = await get_upstream_credentials(selected.upstream, db)

        # Build route context
        route_ctx = build_route_context(
            request_id=request_id,
            trace_id=trace_id,
            auth_ctx=auth_ctx,
            endpoint=endpoint,
            virtual_model=model,
            upstream=selected.upstream,
            upstream_model=selected.upstream_model,
            credentials=credentials,
            route=selected.route
        )

        if stream:
            # Streaming response
            return StreamingResponse(
                stream_response(route_ctx, body, selected.upstream, timer),
                media_type="text/event-stream",
                headers={
                    "X-Request-ID": request_id,
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            # Non-streaming response
            response = await execute_upstream_request(route_ctx, body, selected.upstream)
            adapter = get_adapter(selected.upstream.type.value)
            result = await adapter.parse_upstream_response(response, route_ctx)

            timer.stop()

            # Log request
            usage = result.get("usage", {})
            await log_request(
                db=db,
                request_id=request_id,
                trace_id=trace_id,
                auth_ctx=auth_ctx,
                endpoint=endpoint,
                virtual_model=model,
                upstream=selected.upstream,
                upstream_model=selected.upstream_model,
                status_code=200,
                error_type=None,
                error_message=None,
                timer=timer,
                usage=usage
            )

            return JSONResponse(
                content=result,
                headers={"X-Request-ID": request_id}
            )

    except NoRouteFoundError as e:
        timer.stop()
        await log_request(
            db=db, request_id=request_id, trace_id=trace_id,
            auth_ctx=auth_ctx, endpoint=endpoint, virtual_model=model,
            upstream=None, upstream_model=None, status_code=404,
            error_type="no_route", error_message=str(e), timer=timer
        )
        raise HTTPException(status_code=404, detail={
            "error": {"message": str(e), "type": "not_found_error"}
        })
    except NoHealthyUpstreamError as e:
        timer.stop()
        await log_request(
            db=db, request_id=request_id, trace_id=trace_id,
            auth_ctx=auth_ctx, endpoint=endpoint, virtual_model=model,
            upstream=None, upstream_model=None, status_code=503,
            error_type="no_healthy_upstream", error_message=str(e), timer=timer
        )
        raise HTTPException(status_code=503, detail={
            "error": {"message": str(e), "type": "service_unavailable"}
        })
    except AdapterError as e:
        timer.stop()
        raise HTTPException(status_code=e.status_code, detail=e.to_openai_error())
    except Exception as e:
        timer.stop()
        raise HTTPException(status_code=500, detail={
            "error": {"message": str(e), "type": "internal_error"}
        })


@router.post("/embeddings")
async def embeddings(
    request: Request,
    auth_ctx: AuthContext = Depends(get_auth_context),
    routing_engine: RoutingEngine = Depends(get_routing_engine),
    db: AsyncSession = Depends(get_db)
):
    """
    Create embeddings for text input.

    Compatible with OpenAI's /v1/embeddings endpoint.
    """
    timer = RequestTimer()
    timer.start()

    request_id = generate_request_id()
    trace_id = request.headers.get("X-Trace-ID")
    endpoint = "/v1/embeddings"

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={
            "error": {"message": "Invalid JSON body", "type": "invalid_request_error"}
        })

    model = body.get("model")
    if not model:
        raise HTTPException(status_code=400, detail={
            "error": {"message": "Missing 'model' field", "type": "invalid_request_error"}
        })

    try:
        routing_ctx = RoutingContext(
            endpoint=endpoint,
            virtual_model=model,
            tenant_id=auth_ctx.tenant_id,
            api_key_id=auth_ctx.api_key_id
        )
        selected = routing_engine.select_route(routing_ctx)

        credentials = await get_upstream_credentials(selected.upstream, db)

        route_ctx = build_route_context(
            request_id=request_id,
            trace_id=trace_id,
            auth_ctx=auth_ctx,
            endpoint=endpoint,
            virtual_model=model,
            upstream=selected.upstream,
            upstream_model=selected.upstream_model,
            credentials=credentials,
            route=selected.route
        )

        response = await execute_upstream_request(route_ctx, body, selected.upstream)
        adapter = get_adapter(selected.upstream.type.value)
        result = await adapter.parse_upstream_response(response, route_ctx)

        timer.stop()

        usage = result.get("usage", {})
        await log_request(
            db=db, request_id=request_id, trace_id=trace_id,
            auth_ctx=auth_ctx, endpoint=endpoint, virtual_model=model,
            upstream=selected.upstream, upstream_model=selected.upstream_model,
            status_code=200, error_type=None, error_message=None,
            timer=timer, usage=usage
        )

        return JSONResponse(
            content=result,
            headers={"X-Request-ID": request_id}
        )

    except (NoRouteFoundError, NoHealthyUpstreamError, AdapterError) as e:
        timer.stop()
        if isinstance(e, AdapterError):
            raise HTTPException(status_code=e.status_code, detail=e.to_openai_error())
        raise HTTPException(status_code=503, detail={
            "error": {"message": str(e), "type": "service_unavailable"}
        })


@router.post("/images/generations")
async def images_generations(
    request: Request,
    auth_ctx: AuthContext = Depends(get_auth_context),
    routing_engine: RoutingEngine = Depends(get_routing_engine),
    db: AsyncSession = Depends(get_db)
):
    """
    Create images from a text prompt.

    Compatible with OpenAI's /v1/images/generations endpoint.
    """
    timer = RequestTimer()
    timer.start()

    request_id = generate_request_id()
    trace_id = request.headers.get("X-Trace-ID")
    endpoint = "/v1/images/generations"

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={
            "error": {"message": "Invalid JSON body", "type": "invalid_request_error"}
        })

    model = body.get("model", "dall-e-3")

    try:
        routing_ctx = RoutingContext(
            endpoint=endpoint,
            virtual_model=model,
            tenant_id=auth_ctx.tenant_id,
            api_key_id=auth_ctx.api_key_id
        )
        selected = routing_engine.select_route(routing_ctx)

        credentials = await get_upstream_credentials(selected.upstream, db)

        route_ctx = build_route_context(
            request_id=request_id,
            trace_id=trace_id,
            auth_ctx=auth_ctx,
            endpoint=endpoint,
            virtual_model=model,
            upstream=selected.upstream,
            upstream_model=selected.upstream_model,
            credentials=credentials,
            route=selected.route
        )

        response = await execute_upstream_request(route_ctx, body, selected.upstream)
        adapter = get_adapter(selected.upstream.type.value)
        result = await adapter.parse_upstream_response(response, route_ctx)

        timer.stop()

        await log_request(
            db=db, request_id=request_id, trace_id=trace_id,
            auth_ctx=auth_ctx, endpoint=endpoint, virtual_model=model,
            upstream=selected.upstream, upstream_model=selected.upstream_model,
            status_code=200, error_type=None, error_message=None,
            timer=timer
        )

        return JSONResponse(
            content=result,
            headers={"X-Request-ID": request_id}
        )

    except (NoRouteFoundError, NoHealthyUpstreamError, AdapterError) as e:
        timer.stop()
        if isinstance(e, AdapterError):
            raise HTTPException(status_code=e.status_code, detail=e.to_openai_error())
        raise HTTPException(status_code=503, detail={
            "error": {"message": str(e), "type": "service_unavailable"}
        })


@router.post("/rerank")
async def rerank(
    request: Request,
    auth_ctx: AuthContext = Depends(get_auth_context),
    routing_engine: RoutingEngine = Depends(get_routing_engine),
    db: AsyncSession = Depends(get_db)
):
    """
    Rerank documents based on relevance to a query.

    Extension endpoint (not standard OpenAI).
    Compatible with Cohere's rerank API format.
    """
    timer = RequestTimer()
    timer.start()

    request_id = generate_request_id()
    trace_id = request.headers.get("X-Trace-ID")
    endpoint = "/v1/rerank"

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={
            "error": {"message": "Invalid JSON body", "type": "invalid_request_error"}
        })

    model = body.get("model")
    if not model:
        raise HTTPException(status_code=400, detail={
            "error": {"message": "Missing 'model' field", "type": "invalid_request_error"}
        })

    try:
        routing_ctx = RoutingContext(
            endpoint=endpoint,
            virtual_model=model,
            tenant_id=auth_ctx.tenant_id,
            api_key_id=auth_ctx.api_key_id
        )
        selected = routing_engine.select_route(routing_ctx)

        credentials = await get_upstream_credentials(selected.upstream, db)

        route_ctx = build_route_context(
            request_id=request_id,
            trace_id=trace_id,
            auth_ctx=auth_ctx,
            endpoint=endpoint,
            virtual_model=model,
            upstream=selected.upstream,
            upstream_model=selected.upstream_model,
            credentials=credentials,
            route=selected.route
        )

        response = await execute_upstream_request(route_ctx, body, selected.upstream)
        adapter = get_adapter(selected.upstream.type.value)
        result = await adapter.parse_upstream_response(response, route_ctx)

        timer.stop()

        await log_request(
            db=db, request_id=request_id, trace_id=trace_id,
            auth_ctx=auth_ctx, endpoint=endpoint, virtual_model=model,
            upstream=selected.upstream, upstream_model=selected.upstream_model,
            status_code=200, error_type=None, error_message=None,
            timer=timer
        )

        return JSONResponse(
            content=result,
            headers={"X-Request-ID": request_id}
        )

    except (NoRouteFoundError, NoHealthyUpstreamError, AdapterError) as e:
        timer.stop()
        if isinstance(e, AdapterError):
            raise HTTPException(status_code=e.status_code, detail=e.to_openai_error())
        raise HTTPException(status_code=503, detail={
            "error": {"message": str(e), "type": "service_unavailable"}
        })


@router.get("/models")
async def list_models(
    auth_ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db)
):
    """
    List available models.

    Returns virtual models that the authenticated API key can access.
    Compatible with OpenAI's /v1/models endpoint.
    """
    # Fetch enabled virtual models
    stmt = select(GatewayVirtualModel).where(
        GatewayVirtualModel.tenant_id == auth_ctx.tenant_id,
        GatewayVirtualModel.enabled == True
    )
    result = await db.execute(stmt)
    models = result.scalars().all()

    # Filter by allowed models if key has restrictions
    if auth_ctx.allowed_models:
        import fnmatch
        models = [
            m for m in models
            if any(fnmatch.fnmatch(m.name, pattern) for pattern in auth_ctx.allowed_models)
        ]

    # Format response
    data = []
    for model in models:
        metadata = model.model_metadata or {}
        data.append({
            "id": model.name,
            "object": "model",
            "created": int(model.created_at.timestamp()) if model.created_at else 0,
            "owned_by": metadata.get("owned_by", "organization"),
            "permission": metadata.get("permission", []),
            "root": model.name,
            "parent": None
        })

    return {
        "object": "list",
        "data": data
    }
