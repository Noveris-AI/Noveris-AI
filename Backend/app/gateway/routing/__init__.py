"""
Gateway Routing Package.

This module provides the routing logic for the AI Gateway:
- Policy matching
- Upstream selection
- Circuit breaker management
- Load balancing

Usage:
    from app.gateway.routing import RoutingEngine, RoutingContext

    engine = RoutingEngine(routes, upstreams, virtual_models)
    result = engine.select_route(RoutingContext(
        endpoint="/v1/chat/completions",
        virtual_model="gpt-4",
        tenant_id=tenant_id
    ))
"""

from app.gateway.routing.engine import (
    RoutingEngine,
    RoutingContext,
    SelectedRoute,
    PolicyMatcher,
    UpstreamSelector,
    CircuitBreaker,
    CircuitBreakerRegistry,
    get_circuit_breaker_registry,
    NoRouteFoundError,
    NoHealthyUpstreamError,
    WeightedUpstream,
)

__all__ = [
    "RoutingEngine",
    "RoutingContext",
    "SelectedRoute",
    "PolicyMatcher",
    "UpstreamSelector",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "get_circuit_breaker_registry",
    "NoRouteFoundError",
    "NoHealthyUpstreamError",
    "WeightedUpstream",
]
