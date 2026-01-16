"""
Gateway Routing Engine.

This module implements the core routing logic for the AI Gateway:
- Policy matching based on endpoint, model, tenant, API key, and tags
- Upstream selection with weighted random and fallback support
- Circuit breaker integration
- Route caching for performance

The routing engine is the heart of the gateway's request distribution system.
"""

import asyncio
import fnmatch
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.models.gateway import (
    GatewayRoute,
    GatewayUpstream,
    GatewayVirtualModel,
)


@dataclass
class RoutingContext:
    """Context information for routing decisions."""

    endpoint: str
    virtual_model: str
    tenant_id: UUID
    api_key_id: Optional[UUID] = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SelectedRoute:
    """Result of route selection."""

    route: GatewayRoute
    upstream: GatewayUpstream
    upstream_model: str
    is_fallback: bool = False
    selection_reason: str = ""


@dataclass
class WeightedUpstream:
    """Upstream with weight for load balancing."""

    upstream_id: UUID
    weight: int


class CircuitBreaker:
    """
    Circuit breaker for upstream health management.

    States:
    - CLOSED: Normal operation, requests flow through
    - OPEN: Upstream is unhealthy, requests fail fast
    - HALF_OPEN: Testing if upstream recovered

    Transitions:
    - CLOSED -> OPEN: After failure_threshold consecutive failures
    - OPEN -> HALF_OPEN: After timeout_seconds
    - HALF_OPEN -> CLOSED: After success_threshold successes
    - HALF_OPEN -> OPEN: On any failure
    """

    CLOSED = 0
    OPEN = 1
    HALF_OPEN = 2

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout_seconds: int = 60,
        half_open_max_requests: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_requests = half_open_max_requests

        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_requests = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> int:
        """Get current state, checking for timeout transition."""
        if self._state == self.OPEN and self._last_failure_time:
            if time.time() - self._last_failure_time >= self.timeout_seconds:
                return self.HALF_OPEN
        return self._state

    def is_healthy(self) -> bool:
        """Check if requests should be allowed through."""
        state = self.state
        if state == self.CLOSED:
            return True
        if state == self.HALF_OPEN:
            return self._half_open_requests < self.half_open_max_requests
        return False

    async def record_success(self) -> None:
        """Record a successful request."""
        async with self._lock:
            if self._state == self.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = self.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._half_open_requests = 0
            else:
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Record a failed request."""
        async with self._lock:
            self._last_failure_time = time.time()

            if self._state == self.HALF_OPEN:
                self._state = self.OPEN
                self._success_count = 0
                self._half_open_requests = 0
            else:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = self.OPEN

    async def on_request_start(self) -> bool:
        """Called when a request starts. Returns True if allowed."""
        async with self._lock:
            state = self.state
            if state == self.CLOSED:
                return True
            if state == self.HALF_OPEN:
                if self._half_open_requests < self.half_open_max_requests:
                    self._half_open_requests += 1
                    return True
            return False


class CircuitBreakerRegistry:
    """Registry of circuit breakers for upstreams."""

    def __init__(self):
        self._breakers: Dict[UUID, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        upstream_id: UUID,
        config: Optional[Dict[str, Any]] = None
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for an upstream."""
        async with self._lock:
            if upstream_id not in self._breakers:
                config = config or {}
                self._breakers[upstream_id] = CircuitBreaker(
                    failure_threshold=config.get("failure_threshold", 5),
                    success_threshold=config.get("success_threshold", 3),
                    timeout_seconds=config.get("timeout_seconds", 60),
                    half_open_max_requests=config.get("half_open_max_requests", 3)
                )
            return self._breakers[upstream_id]

    def is_healthy(self, upstream_id: UUID) -> bool:
        """Check if an upstream is healthy."""
        if upstream_id not in self._breakers:
            return True  # Unknown upstreams are assumed healthy
        return self._breakers[upstream_id].is_healthy()


# Global circuit breaker registry
_circuit_breaker_registry = CircuitBreakerRegistry()


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    return _circuit_breaker_registry


class PolicyMatcher:
    """
    Matches requests to routing policies.

    Policies are evaluated in priority order (lower number = higher priority).
    First matching policy wins.

    Match conditions support:
    - Exact match: "endpoint": "/v1/chat/completions"
    - Wildcard: "virtual_model": "openai/*"
    - UUID: "tenant_id": "uuid-string"
    - Tags: "tags": {"tier": "premium"}
    """

    def matches(
        self,
        route: GatewayRoute,
        ctx: RoutingContext
    ) -> Tuple[bool, str]:
        """
        Check if a route matches the routing context.

        Returns:
            Tuple of (matches, reason)
        """
        match_config = route.match or {}

        # Check endpoint match
        if "endpoint" in match_config:
            if not fnmatch.fnmatch(ctx.endpoint, match_config["endpoint"]):
                return False, f"endpoint mismatch: {ctx.endpoint} != {match_config['endpoint']}"

        # Check virtual model match (supports wildcards)
        if "virtual_model" in match_config:
            pattern = match_config["virtual_model"]
            if not fnmatch.fnmatch(ctx.virtual_model, pattern):
                return False, f"model mismatch: {ctx.virtual_model} != {pattern}"

        # Check tenant ID match
        if "tenant_id" in match_config:
            expected_tenant = match_config["tenant_id"]
            if isinstance(expected_tenant, str):
                expected_tenant = UUID(expected_tenant)
            if ctx.tenant_id != expected_tenant:
                return False, f"tenant mismatch"

        # Check API key ID match
        if "api_key_id" in match_config:
            if ctx.api_key_id is None:
                return False, "api_key_id required but not provided"
            expected_key = match_config["api_key_id"]
            if isinstance(expected_key, str):
                expected_key = UUID(expected_key)
            if ctx.api_key_id != expected_key:
                return False, "api_key_id mismatch"

        # Check tags match (all specified tags must match)
        if "tags" in match_config:
            required_tags = match_config["tags"]
            for key, value in required_tags.items():
                if ctx.tags.get(key) != value:
                    return False, f"tag mismatch: {key}"

        return True, "all conditions matched"


class UpstreamSelector:
    """
    Selects upstreams based on routing policy action.

    Supports:
    - Weighted random selection among primary upstreams
    - Fallback chain when primaries are unhealthy
    - Circuit breaker integration
    """

    def __init__(self, circuit_breakers: CircuitBreakerRegistry):
        self.circuit_breakers = circuit_breakers

    def select(
        self,
        route: GatewayRoute,
        upstreams: Dict[UUID, GatewayUpstream]
    ) -> Tuple[Optional[GatewayUpstream], bool, str]:
        """
        Select an upstream based on route action.

        Args:
            route: The matched routing policy
            upstreams: Dict of available upstreams by ID

        Returns:
            Tuple of (selected_upstream, is_fallback, selection_reason)
        """
        action = route.action or {}

        # Get primary upstreams with weights
        primaries = action.get("primary_upstreams", [])

        # Filter healthy primaries
        healthy_primaries = []
        for primary in primaries:
            upstream_id = primary.get("upstream_id")
            if isinstance(upstream_id, str):
                upstream_id = UUID(upstream_id)

            if upstream_id not in upstreams:
                continue

            upstream = upstreams[upstream_id]
            if not upstream.enabled:
                continue

            if not self.circuit_breakers.is_healthy(upstream_id):
                continue

            healthy_primaries.append({
                "upstream": upstream,
                "weight": primary.get("weight", 1)
            })

        # Select from healthy primaries using weighted random
        if healthy_primaries:
            upstream = self._weighted_random_select(healthy_primaries)
            return upstream, False, "selected from primary upstreams"

        # Try fallback chain
        fallbacks = action.get("fallback_upstreams", [])
        for fallback_id in fallbacks:
            if isinstance(fallback_id, str):
                fallback_id = UUID(fallback_id)

            if fallback_id not in upstreams:
                continue

            upstream = upstreams[fallback_id]
            if not upstream.enabled:
                continue

            if not self.circuit_breakers.is_healthy(fallback_id):
                continue

            return upstream, True, f"fallback to {upstream.name}"

        return None, False, "no healthy upstreams available"

    def _weighted_random_select(
        self,
        candidates: List[Dict[str, Any]]
    ) -> GatewayUpstream:
        """Select randomly based on weights."""
        total_weight = sum(c["weight"] for c in candidates)
        if total_weight <= 0:
            return candidates[0]["upstream"]

        r = random.uniform(0, total_weight)
        current = 0
        for candidate in candidates:
            current += candidate["weight"]
            if r <= current:
                return candidate["upstream"]

        return candidates[-1]["upstream"]


class RoutingEngine:
    """
    Main routing engine that combines policy matching and upstream selection.

    Usage:
        engine = RoutingEngine(routes, upstreams, virtual_models)
        result = engine.select_route(routing_context)
    """

    def __init__(
        self,
        routes: List[GatewayRoute],
        upstreams: Dict[UUID, GatewayUpstream],
        virtual_models: Dict[str, GatewayVirtualModel],
        circuit_breakers: Optional[CircuitBreakerRegistry] = None
    ):
        # Sort routes by priority
        self.routes = sorted(routes, key=lambda r: r.priority)
        self.upstreams = upstreams
        self.virtual_models = virtual_models

        self.policy_matcher = PolicyMatcher()
        self.upstream_selector = UpstreamSelector(
            circuit_breakers or get_circuit_breaker_registry()
        )

    def select_route(self, ctx: RoutingContext) -> SelectedRoute:
        """
        Select the best route and upstream for a request.

        Args:
            ctx: Routing context with endpoint, model, tenant, etc.

        Returns:
            SelectedRoute with the chosen route and upstream

        Raises:
            NoRouteFoundError: If no route matches
            NoHealthyUpstreamError: If all upstreams are unhealthy
        """
        # Find matching route
        matched_route = None
        match_reason = ""

        for route in self.routes:
            if not route.enabled:
                continue

            matches, reason = self.policy_matcher.matches(route, ctx)
            if matches:
                matched_route = route
                match_reason = reason
                break

        # If no route found, try virtual model's default route
        if not matched_route:
            virtual_model = self.virtual_models.get(ctx.virtual_model)
            if virtual_model and virtual_model.default_route_id:
                for route in self.routes:
                    if route.id == virtual_model.default_route_id:
                        matched_route = route
                        match_reason = "using virtual model default route"
                        break

        if not matched_route:
            raise NoRouteFoundError(
                f"No route found for endpoint={ctx.endpoint}, model={ctx.virtual_model}"
            )

        # Select upstream
        upstream, is_fallback, selection_reason = self.upstream_selector.select(
            matched_route,
            self.upstreams
        )

        if not upstream:
            raise NoHealthyUpstreamError(
                f"No healthy upstream for route {matched_route.name}"
            )

        # Determine upstream model name
        upstream_model = self._get_upstream_model(ctx.virtual_model, upstream)

        return SelectedRoute(
            route=matched_route,
            upstream=upstream,
            upstream_model=upstream_model,
            is_fallback=is_fallback,
            selection_reason=f"{match_reason}; {selection_reason}"
        )

    def _get_upstream_model(
        self,
        virtual_model: str,
        upstream: GatewayUpstream
    ) -> str:
        """Get the actual model name to use with the upstream."""
        # Check model mapping
        model_mapping = upstream.model_mapping or {}

        # Exact match
        if virtual_model in model_mapping:
            return model_mapping[virtual_model]

        # Try without namespace prefix (e.g., "openai/gpt-4" -> "gpt-4")
        if "/" in virtual_model:
            short_name = virtual_model.split("/", 1)[1]
            if short_name in model_mapping:
                return model_mapping[short_name]

        # Return virtual model as-is (upstream should handle it)
        return virtual_model

    def dry_run(self, ctx: RoutingContext) -> Dict[str, Any]:
        """
        Perform a dry run to show routing decision without executing.

        Useful for debugging and route testing.

        Returns:
            Dict with routing decision details
        """
        result = {
            "context": {
                "endpoint": ctx.endpoint,
                "virtual_model": ctx.virtual_model,
                "tenant_id": str(ctx.tenant_id),
                "api_key_id": str(ctx.api_key_id) if ctx.api_key_id else None,
                "tags": ctx.tags,
            },
            "evaluated_routes": [],
            "selected_route": None,
            "selected_upstream": None,
            "error": None,
        }

        # Evaluate all routes
        for route in self.routes:
            matches, reason = self.policy_matcher.matches(route, ctx)
            result["evaluated_routes"].append({
                "route_id": str(route.id),
                "route_name": route.name,
                "priority": route.priority,
                "enabled": route.enabled,
                "matches": matches,
                "reason": reason,
            })

        # Try to select route
        try:
            selected = self.select_route(ctx)
            result["selected_route"] = {
                "route_id": str(selected.route.id),
                "route_name": selected.route.name,
            }
            result["selected_upstream"] = {
                "upstream_id": str(selected.upstream.id),
                "upstream_name": selected.upstream.name,
                "upstream_type": selected.upstream.type.value,
                "upstream_model": selected.upstream_model,
                "is_fallback": selected.is_fallback,
                "selection_reason": selected.selection_reason,
            }
        except (NoRouteFoundError, NoHealthyUpstreamError) as e:
            result["error"] = str(e)

        return result


class NoRouteFoundError(Exception):
    """Raised when no route matches the request."""
    pass


class NoHealthyUpstreamError(Exception):
    """Raised when all upstreams are unhealthy."""
    pass
