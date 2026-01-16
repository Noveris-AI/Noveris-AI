"""
MCP Client Manager Service.

This module provides a unified interface for managing MCP (Model Context Protocol)
client connections and tool invocations.

Features:
- Support for multiple transport types (stdio, SSE, Streamable HTTP)
- Connection pooling and lifecycle management
- Tool discovery and caching
- Audit logging for all tool calls
- Rate limiting per server

References:
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- MCP Specification: https://modelcontextprotocol.io/
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chat import ChatMCPServer, ChatMCPToolCall, MCPServerStatus, MCPTransport

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class MCPTool:
    """Represents an MCP tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_id: UUID
    server_name: str


@dataclass
class MCPToolResult:
    """Result from an MCP tool invocation."""
    success: bool
    content: Any
    error: Optional[str] = None
    latency_ms: int = 0
    tool_call_id: Optional[str] = None


@dataclass
class MCPServerConnection:
    """Manages a connection to an MCP server."""
    server_id: UUID
    server_name: str
    transport: MCPTransport
    connection_config: Dict[str, Any]
    tools: List[MCPTool] = field(default_factory=list)
    is_connected: bool = False
    last_error: Optional[str] = None
    _client: Optional[Any] = None
    _http_client: Optional[httpx.AsyncClient] = None


# =============================================================================
# MCP Client Manager
# =============================================================================

class MCPClientManager:
    """
    Manages MCP server connections and tool invocations.

    This class handles:
    - Establishing connections to MCP servers
    - Discovering available tools
    - Executing tool calls
    - Connection lifecycle management
    - Rate limiting and error handling
    """

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self._connections: Dict[UUID, MCPServerConnection] = {}
        self._tools_cache: Dict[str, MCPTool] = {}
        self._rate_limiters: Dict[UUID, "RateLimiter"] = {}

    async def initialize(self) -> None:
        """Initialize MCP client manager and load enabled servers."""
        if not settings.mcp.enabled:
            logger.info("MCP is globally disabled")
            return

        # Load enabled servers from database
        stmt = select(ChatMCPServer).where(
            ChatMCPServer.tenant_id == self.tenant_id,
            ChatMCPServer.enabled == True
        ).order_by(ChatMCPServer.display_order)

        result = await self.db.execute(stmt)
        servers = result.scalars().all()

        for server in servers:
            try:
                await self._setup_server_connection(server)
            except Exception as e:
                logger.error(f"Failed to setup MCP server {server.name}: {e}")

    async def _setup_server_connection(self, server: ChatMCPServer) -> None:
        """Setup a connection to an MCP server."""
        connection = MCPServerConnection(
            server_id=server.id,
            server_name=server.name,
            transport=server.transport,
            connection_config=server.connection_config or {}
        )

        # Setup rate limiter
        rate_config = server.rate_limit or {}
        self._rate_limiters[server.id] = RateLimiter(
            max_calls=rate_config.get("calls_per_minute", settings.mcp.rate_limit_calls_per_minute),
            window_seconds=60
        )

        self._connections[server.id] = connection

        # Try to connect and discover tools
        try:
            await self._connect_server(connection)
            tools = await self._discover_tools(connection)
            connection.tools = tools
            connection.is_connected = True

            # Update tools cache
            for tool in tools:
                self._tools_cache[f"{server.name}:{tool.name}"] = tool

            # Update database with cached tools
            await self._update_server_status(server.id, MCPServerStatus.ACTIVE, tools)

        except Exception as e:
            connection.last_error = str(e)
            await self._update_server_status(server.id, MCPServerStatus.ERROR, error=str(e))
            logger.warning(f"MCP server {server.name} connection failed: {e}")

    async def _connect_server(self, connection: MCPServerConnection) -> None:
        """Establish connection to MCP server based on transport type."""
        if connection.transport == MCPTransport.STREAMABLE_HTTP:
            # HTTP/SSE transport - use httpx client
            base_url = connection.connection_config.get("url", "")
            if not base_url:
                raise ValueError("Missing 'url' in connection config for HTTP transport")

            # Validate URL is in allowed hosts
            self._validate_server_url(base_url)

            connection._http_client = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(settings.mcp.web_search_timeout_ms / 1000)
            )

        elif connection.transport == MCPTransport.SSE:
            # SSE transport
            base_url = connection.connection_config.get("url", "")
            if not base_url:
                raise ValueError("Missing 'url' in connection config for SSE transport")

            self._validate_server_url(base_url)

            connection._http_client = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(settings.mcp.web_search_timeout_ms / 1000)
            )

        elif connection.transport == MCPTransport.STDIO:
            # STDIO transport - would require subprocess management
            # For now, we focus on HTTP-based transports
            logger.info(f"STDIO transport for {connection.server_name} - skipping connection")

    def _validate_server_url(self, url: str) -> None:
        """Validate server URL against allowed hosts."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname

        if host not in settings.mcp.allowed_hosts_list:
            raise ValueError(f"MCP server host '{host}' is not in allowed hosts list")

    async def _discover_tools(self, connection: MCPServerConnection) -> List[MCPTool]:
        """Discover available tools from MCP server."""
        tools = []

        if connection.transport in (MCPTransport.STREAMABLE_HTTP, MCPTransport.SSE):
            if connection._http_client is None:
                return tools

            try:
                # MCP tool discovery via tools/list endpoint
                response = await connection._http_client.post(
                    "/mcp/tools/list",
                    json={"method": "tools/list"}
                )
                response.raise_for_status()
                data = response.json()

                for tool_data in data.get("tools", []):
                    tools.append(MCPTool(
                        name=tool_data["name"],
                        description=tool_data.get("description", ""),
                        input_schema=tool_data.get("inputSchema", {}),
                        server_id=connection.server_id,
                        server_name=connection.server_name
                    ))

            except Exception as e:
                logger.warning(f"Failed to discover tools from {connection.server_name}: {e}")

        return tools

    async def _update_server_status(
        self,
        server_id: UUID,
        status: MCPServerStatus,
        tools: Optional[List[MCPTool]] = None,
        error: Optional[str] = None
    ) -> None:
        """Update server status in database."""
        update_data = {
            "status": status,
            "last_health_check": datetime.now(timezone.utc),
            "health_check_error": error
        }

        if tools is not None:
            update_data["tools_cache"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema
                }
                for t in tools
            ]
            update_data["tools_cache_updated_at"] = datetime.now(timezone.utc)

        stmt = update(ChatMCPServer).where(
            ChatMCPServer.id == server_id
        ).values(**update_data)

        await self.db.execute(stmt)
        await self.db.commit()

    async def list_tools(self) -> List[MCPTool]:
        """List all available tools across all connected servers."""
        return list(self._tools_cache.values())

    async def get_tools_for_openai(self) -> List[Dict[str, Any]]:
        """Get tools formatted for OpenAI tool_calls format."""
        tools = []
        for tool in self._tools_cache.values():
            tools.append({
                "type": "function",
                "function": {
                    "name": f"{tool.server_name}__{tool.name}",
                    "description": tool.description,
                    "parameters": tool.input_schema
                }
            })
        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> MCPToolResult:
        """
        Call an MCP tool.

        Args:
            tool_name: Full tool name in format "server_name__tool_name"
            arguments: Tool arguments
            context: Optional context (conversation_id, message_id, user_id)

        Returns:
            MCPToolResult with the tool execution result
        """
        start_time = time.time()

        # Parse tool name to find server
        if "__" in tool_name:
            server_name, actual_tool_name = tool_name.split("__", 1)
        else:
            # Try to find in cache
            for key, tool in self._tools_cache.items():
                if tool.name == tool_name:
                    server_name = tool.server_name
                    actual_tool_name = tool_name
                    break
            else:
                return MCPToolResult(
                    success=False,
                    content=None,
                    error=f"Tool '{tool_name}' not found"
                )

        # Find the tool
        cache_key = f"{server_name}:{actual_tool_name}"
        tool = self._tools_cache.get(cache_key)

        if not tool:
            return MCPToolResult(
                success=False,
                content=None,
                error=f"Tool '{actual_tool_name}' not found in server '{server_name}'"
            )

        # Get connection
        connection = self._connections.get(tool.server_id)
        if not connection or not connection.is_connected:
            return MCPToolResult(
                success=False,
                content=None,
                error=f"Server '{server_name}' is not connected"
            )

        # Check rate limit
        rate_limiter = self._rate_limiters.get(tool.server_id)
        if rate_limiter and not await rate_limiter.check():
            return MCPToolResult(
                success=False,
                content=None,
                error=f"Rate limit exceeded for server '{server_name}'"
            )

        # Execute tool call
        tool_call_id = str(uuid4())
        result = None
        error = None
        status = "success"

        try:
            result = await self._execute_tool_call(connection, actual_tool_name, arguments)
        except Exception as e:
            error = str(e)
            status = "error"
            logger.error(f"Tool call failed: {e}")

        latency_ms = int((time.time() - start_time) * 1000)

        # Audit log
        if settings.mcp.audit_tool_calls:
            await self._audit_tool_call(
                context=context or {},
                server_id=tool.server_id,
                server_name=server_name,
                tool_name=actual_tool_name,
                tool_call_id=tool_call_id,
                arguments=arguments,
                result=result,
                status=status,
                error=error,
                latency_ms=latency_ms
            )

        return MCPToolResult(
            success=error is None,
            content=result,
            error=error,
            latency_ms=latency_ms,
            tool_call_id=tool_call_id
        )

    async def _execute_tool_call(
        self,
        connection: MCPServerConnection,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Execute a tool call on the MCP server."""
        if connection._http_client is None:
            raise RuntimeError("HTTP client not initialized")

        # MCP tools/call endpoint
        response = await connection._http_client.post(
            "/mcp/tools/call",
            json={
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
        )
        response.raise_for_status()
        data = response.json()

        # Extract result content
        if "content" in data:
            content = data["content"]
            if isinstance(content, list) and len(content) > 0:
                # MCP returns content as array of content blocks
                text_parts = []
                for block in content:
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                return "\n".join(text_parts) if text_parts else content
            return content

        return data.get("result")

    async def _audit_tool_call(
        self,
        context: Dict[str, Any],
        server_id: UUID,
        server_name: str,
        tool_name: str,
        tool_call_id: str,
        arguments: Dict[str, Any],
        result: Any,
        status: str,
        error: Optional[str],
        latency_ms: int
    ) -> None:
        """Record tool call to audit log."""
        # Optionally redact arguments
        logged_args = arguments
        if settings.mcp.audit_redact_arguments:
            logged_args = {"redacted": True}
            args_redacted = True
        else:
            args_redacted = False

        # Truncate result if too large
        result_data = result
        result_truncated = False
        if result:
            result_str = json.dumps(result) if not isinstance(result, str) else result
            if len(result_str) > settings.mcp.audit_max_result_size:
                result_data = result_str[:settings.mcp.audit_max_result_size] + "...[truncated]"
                result_truncated = True

        tool_call_log = ChatMCPToolCall(
            tenant_id=self.tenant_id,
            conversation_id=context.get("conversation_id"),
            message_id=context.get("message_id"),
            user_id=context.get("user_id"),
            mcp_server_id=server_id,
            mcp_server_name=server_name,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            arguments=logged_args,
            arguments_redacted=args_redacted,
            result={"content": result_data} if result_data else None,
            result_truncated=result_truncated,
            status=status,
            error_message=error,
            latency_ms=latency_ms
        )

        self.db.add(tool_call_log)
        await self.db.commit()

    async def close(self) -> None:
        """Close all MCP server connections."""
        for connection in self._connections.values():
            if connection._http_client:
                await connection._http_client.aclose()
                connection._http_client = None
            connection.is_connected = False

        self._connections.clear()
        self._tools_cache.clear()


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: List[float] = []

    async def check(self) -> bool:
        """Check if rate limit allows another call."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Remove old calls
        self._calls = [t for t in self._calls if t > cutoff]

        if len(self._calls) >= self.max_calls:
            return False

        self._calls.append(now)
        return True


# =============================================================================
# Context Manager for MCP Client
# =============================================================================

@asynccontextmanager
async def get_mcp_client(
    db: AsyncSession,
    tenant_id: UUID
) -> AsyncIterator[MCPClientManager]:
    """Context manager for MCP client manager."""
    client = MCPClientManager(db, tenant_id)
    try:
        await client.initialize()
        yield client
    finally:
        await client.close()
