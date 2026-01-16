"""
OpenAI Client Service for Chat.

This module provides a unified interface for making OpenAI-compatible API calls
to various model providers (internal gateway, external services, user deployments).

Features:
- Async HTTP client with connection pooling
- Streaming support via SSE
- Retry logic with exponential backoff
- Token usage tracking
- Support for multiple model profiles
- Tool calling support

References:
- OpenAI API: https://platform.openai.com/docs/api-reference/chat
- Streaming: https://platform.openai.com/docs/guides/streaming-responses
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple, Union
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chat import ChatModelProfile
from app.models.gateway import GatewaySecret
from app.gateway.services.secret_manager import SecretManager

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ChatMessage:
    """A chat message for API request."""
    role: str
    content: Union[str, List[Dict[str, Any]]]
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


@dataclass
class ChatCompletionRequest:
    """Request parameters for chat completion."""
    model: str
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None
    stop: Optional[Union[str, List[str]]] = None
    user: Optional[str] = None


@dataclass
class TokenUsage:
    """Token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatCompletionResponse:
    """Response from chat completion."""
    id: str
    model: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class StreamDelta:
    """A delta in streaming response."""
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None


# =============================================================================
# OpenAI Client
# =============================================================================

class OpenAIClient:
    """
    Async OpenAI-compatible API client.

    Supports multiple model profiles and provides a unified interface
    for chat completions, embeddings, and other capabilities.
    """

    def __init__(
        self,
        db: AsyncSession,
        model_profile: ChatModelProfile,
        api_key: Optional[str] = None
    ):
        self.db = db
        self.model_profile = model_profile
        self.api_key = api_key
        self.base_url = model_profile.base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {}

            # Add authorization if API key is available
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Add custom headers from profile
            if self.model_profile.headers:
                headers.update(self.model_profile.headers)

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.model_profile.timeout_ms / 1000)
            )

        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat_completions(
        self,
        request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Create a chat completion (non-streaming).

        Args:
            request: Chat completion request parameters

        Returns:
            ChatCompletionResponse with the model's response
        """
        client = await self._get_client()

        # Build request body
        body = self._build_chat_body(request)

        # Make request with retry
        response = await self._request_with_retry(
            client, "POST", "/chat/completions", body
        )

        return self._parse_chat_response(response)

    async def chat_completions_stream(
        self,
        request: ChatCompletionRequest
    ) -> AsyncIterator[StreamDelta]:
        """
        Create a streaming chat completion.

        Args:
            request: Chat completion request parameters (stream=True)

        Yields:
            StreamDelta objects as they arrive
        """
        client = await self._get_client()

        # Build request body with stream=True
        body = self._build_chat_body(request)
        body["stream"] = True

        async with client.stream(
            "POST",
            "/chat/completions",
            json=body
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue

                if line.startswith("data: "):
                    data = line[6:]

                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                        delta = self._parse_stream_chunk(chunk)
                        if delta:
                            yield delta
                    except json.JSONDecodeError:
                        continue

    async def embeddings(
        self,
        input_texts: Union[str, List[str]],
        model: Optional[str] = None
    ) -> List[List[float]]:
        """
        Create embeddings for text input.

        Args:
            input_texts: Text or list of texts to embed
            model: Model to use (defaults to profile's embedding model)

        Returns:
            List of embedding vectors
        """
        client = await self._get_client()

        if isinstance(input_texts, str):
            input_texts = [input_texts]

        body = {
            "input": input_texts,
            "model": model or self.model_profile.default_model
        }

        response = await self._request_with_retry(
            client, "POST", "/embeddings", body
        )

        # Extract embeddings from response
        embeddings = []
        for item in response.get("data", []):
            embeddings.append(item.get("embedding", []))

        return embeddings

    def _build_chat_body(self, request: ChatCompletionRequest) -> Dict[str, Any]:
        """Build request body for chat completion."""
        # Convert messages to API format
        messages = []
        for msg in request.messages:
            message = {"role": msg.role}

            if isinstance(msg.content, str):
                message["content"] = msg.content
            else:
                message["content"] = msg.content

            if msg.name:
                message["name"] = msg.name
            if msg.tool_call_id:
                message["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                message["tool_calls"] = msg.tool_calls

            messages.append(message)

        body: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }

        # Add optional parameters
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            body["top_p"] = request.top_p
        if request.frequency_penalty:
            body["frequency_penalty"] = request.frequency_penalty
        if request.presence_penalty:
            body["presence_penalty"] = request.presence_penalty
        if request.tools:
            body["tools"] = request.tools
        if request.tool_choice:
            body["tool_choice"] = request.tool_choice
        if request.response_format:
            body["response_format"] = request.response_format
        if request.stop:
            body["stop"] = request.stop
        if request.user:
            body["user"] = request.user

        return body

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        body: Dict[str, Any],
        max_retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        retries = max_retries or self.model_profile.max_retries or 2
        last_error = None

        for attempt in range(retries + 1):
            try:
                response = await client.request(method, path, json=body)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (429, 500, 502, 503, 504):
                    # Retryable error
                    if attempt < retries:
                        wait_time = 2 ** attempt  # Exponential backoff
                        await asyncio.sleep(wait_time)
                        continue
                raise

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(1)
                    continue
                raise

            except Exception as e:
                last_error = e
                raise

        raise last_error or Exception("Request failed")

    def _parse_chat_response(self, data: Dict[str, Any]) -> ChatCompletionResponse:
        """Parse chat completion response."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage_data = data.get("usage", {})

        return ChatCompletionResponse(
            id=data.get("id", ""),
            model=data.get("model", ""),
            content=message.get("content"),
            tool_calls=message.get("tool_calls"),
            finish_reason=choice.get("finish_reason"),
            usage=TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0)
            ),
            raw_response=data
        )

    def _parse_stream_chunk(self, chunk: Dict[str, Any]) -> Optional[StreamDelta]:
        """Parse a streaming response chunk."""
        choices = chunk.get("choices", [])
        if not choices:
            return None

        delta = choices[0].get("delta", {})
        finish_reason = choices[0].get("finish_reason")

        if not delta and not finish_reason:
            return None

        return StreamDelta(
            content=delta.get("content"),
            tool_calls=delta.get("tool_calls"),
            finish_reason=finish_reason
        )


# =============================================================================
# Model Profile Service
# =============================================================================

class ModelProfileService:
    """Service for managing model profiles."""

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self._secret_manager = SecretManager()

    async def get_profile(self, profile_id: UUID) -> Optional[ChatModelProfile]:
        """Get a model profile by ID."""
        stmt = select(ChatModelProfile).where(
            ChatModelProfile.id == profile_id,
            ChatModelProfile.tenant_id == self.tenant_id,
            ChatModelProfile.enabled == True
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_default_profile(self) -> Optional[ChatModelProfile]:
        """Get the default model profile."""
        stmt = select(ChatModelProfile).where(
            ChatModelProfile.tenant_id == self.tenant_id,
            ChatModelProfile.is_default == True,
            ChatModelProfile.enabled == True
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_profiles(self, capability: Optional[str] = None) -> List[ChatModelProfile]:
        """List all enabled model profiles, optionally filtered by capability."""
        stmt = select(ChatModelProfile).where(
            ChatModelProfile.tenant_id == self.tenant_id,
            ChatModelProfile.enabled == True
        )

        if capability:
            stmt = stmt.where(
                ChatModelProfile.capabilities.contains([capability])
            )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_api_key(self, profile: ChatModelProfile) -> Optional[str]:
        """Get decrypted API key for a model profile."""
        if not profile.api_key_secret_id:
            return None

        stmt = select(GatewaySecret).where(
            GatewaySecret.id == profile.api_key_secret_id
        )
        result = await self.db.execute(stmt)
        secret = result.scalar_one_or_none()

        if not secret:
            return None

        return self._secret_manager.decrypt(secret.ciphertext)

    async def create_client(
        self,
        profile: Optional[ChatModelProfile] = None,
        profile_id: Optional[UUID] = None
    ) -> OpenAIClient:
        """
        Create an OpenAI client for a model profile.

        Args:
            profile: Model profile (if already loaded)
            profile_id: Profile ID to load

        Returns:
            Configured OpenAIClient
        """
        if profile is None:
            if profile_id:
                profile = await self.get_profile(profile_id)
            else:
                profile = await self.get_default_profile()

        if not profile:
            raise ValueError("No model profile found")

        api_key = await self.get_api_key(profile)

        return OpenAIClient(
            db=self.db,
            model_profile=profile,
            api_key=api_key
        )


# =============================================================================
# Factory Functions
# =============================================================================

async def create_openai_client(
    db: AsyncSession,
    tenant_id: UUID,
    profile_id: Optional[UUID] = None
) -> OpenAIClient:
    """Create an OpenAI client for the given tenant and optional profile."""
    service = ModelProfileService(db, tenant_id)
    return await service.create_client(profile_id=profile_id)
