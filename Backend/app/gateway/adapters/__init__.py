"""
AI Gateway Adapters Package.

This module provides adapters for different upstream providers.
Each adapter handles the translation between OpenAI-compatible format
and the provider's native API format.

Available adapters:
- OpenAIAdapter: Official OpenAI API (passthrough)
- OpenAICompatibleAdapter: vLLM, sglang, Xinference, etc.
- CohereRerankAdapter: Cohere Rerank and Embed APIs
- StableDiffusionAdapter: SD WebUI/A1111 image generation
- CustomHTTPAdapter: Template-based custom HTTP integration

Usage:
    from app.gateway.adapters import get_adapter, AdapterBase

    adapter = get_adapter("openai_compatible")
    request = await adapter.build_upstream_request(openai_request, route_ctx)
"""

from typing import Dict, Type

from app.gateway.adapters.base import (
    AdapterBase,
    AdapterError,
    RouteContext,
    UpstreamRequest,
    UpstreamResponse,
)
from app.gateway.adapters.openai import OpenAIAdapter
from app.gateway.adapters.openai_compatible import OpenAICompatibleAdapter
from app.gateway.adapters.cohere_rerank import CohereRerankAdapter
from app.gateway.adapters.stable_diffusion import StableDiffusionAdapter
from app.gateway.adapters.custom_http import CustomHTTPAdapter


# Registry of available adapters
_ADAPTER_REGISTRY: Dict[str, Type[AdapterBase]] = {
    "openai": OpenAIAdapter,
    "openai_compatible": OpenAICompatibleAdapter,
    "anthropic": OpenAICompatibleAdapter,  # Anthropic uses OpenAI-compatible format via adapters
    "gemini": OpenAICompatibleAdapter,      # Google Gemini OpenAI-compatible endpoint
    "cohere": CohereRerankAdapter,
    "stable_diffusion": StableDiffusionAdapter,
    "custom_http": CustomHTTPAdapter,
}

# Singleton instances (adapters are stateless)
_ADAPTER_INSTANCES: Dict[str, AdapterBase] = {}


def get_adapter(adapter_type: str) -> AdapterBase:
    """
    Get an adapter instance by type.

    Args:
        adapter_type: One of the registered adapter types

    Returns:
        AdapterBase instance

    Raises:
        ValueError: If adapter type is not registered
    """
    if adapter_type not in _ADAPTER_REGISTRY:
        raise ValueError(f"Unknown adapter type: {adapter_type}. "
                         f"Available types: {list(_ADAPTER_REGISTRY.keys())}")

    # Use singleton pattern (adapters are stateless)
    if adapter_type not in _ADAPTER_INSTANCES:
        _ADAPTER_INSTANCES[adapter_type] = _ADAPTER_REGISTRY[adapter_type]()

    return _ADAPTER_INSTANCES[adapter_type]


def register_adapter(adapter_type: str, adapter_class: Type[AdapterBase]) -> None:
    """
    Register a new adapter type.

    Args:
        adapter_type: Unique identifier for the adapter
        adapter_class: AdapterBase subclass
    """
    _ADAPTER_REGISTRY[adapter_type] = adapter_class
    # Clear cached instance if exists
    if adapter_type in _ADAPTER_INSTANCES:
        del _ADAPTER_INSTANCES[adapter_type]


def list_adapters() -> Dict[str, Type[AdapterBase]]:
    """Get all registered adapters."""
    return _ADAPTER_REGISTRY.copy()


__all__ = [
    # Base classes
    "AdapterBase",
    "AdapterError",
    "RouteContext",
    "UpstreamRequest",
    "UpstreamResponse",
    # Adapters
    "OpenAIAdapter",
    "OpenAICompatibleAdapter",
    "CohereRerankAdapter",
    "StableDiffusionAdapter",
    "CustomHTTPAdapter",
    # Factory functions
    "get_adapter",
    "register_adapter",
    "list_adapters",
]
