"""
Web Search MCP Server.

This module implements an MCP server that provides web search capabilities
via SearXNG as the backend search engine.

Features:
- Privacy-respecting search via SearXNG
- Configurable search parameters (language, time range, result count)
- Multiple search engines aggregation
- Can be disabled globally via configuration

References:
- SearXNG: https://docs.searxng.org/
- MCP Specification: https://modelcontextprotocol.io/
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Schemas
# =============================================================================

class SearchParams(BaseModel):
    """Parameters for web search."""
    query: str = Field(..., description="Search query string")
    num_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of results to return"
    )
    language: str = Field(
        default="auto",
        description="Language code (e.g., 'en', 'zh', 'auto')"
    )
    time_range: Optional[str] = Field(
        default=None,
        description="Time range filter: 'day', 'week', 'month', 'year'"
    )
    categories: List[str] = Field(
        default_factory=lambda: ["general"],
        description="Search categories: 'general', 'news', 'images', 'videos'"
    )


class SearchResult(BaseModel):
    """A single search result."""
    title: str
    url: str
    snippet: str
    source: Optional[str] = None
    published_date: Optional[str] = None
    thumbnail_url: Optional[str] = None


class SearchResponse(BaseModel):
    """Response from web search."""
    results: List[SearchResult]
    query: str
    total_results: int
    search_time_ms: int
    suggestions: List[str] = []


# =============================================================================
# Web Search Tool
# =============================================================================

class WebSearchTool:
    """
    Web search tool using SearXNG as backend.

    This tool provides privacy-respecting web search capabilities.
    Results are aggregated from multiple search engines.
    """

    def __init__(self, searxng_url: Optional[str] = None):
        self.searxng_url = searxng_url or settings.mcp.web_search_searxng_url
        self.timeout_ms = settings.mcp.web_search_timeout_ms
        self.max_results = settings.mcp.web_search_results_limit

    def is_enabled(self) -> bool:
        """Check if web search is enabled."""
        return settings.mcp.enabled and settings.mcp.web_search_enabled

    async def search(self, params: SearchParams) -> SearchResponse:
        """
        Perform a web search.

        Args:
            params: Search parameters

        Returns:
            SearchResponse with results

        Raises:
            RuntimeError: If web search is disabled
            httpx.HTTPError: If search request fails
        """
        if not self.is_enabled():
            raise RuntimeError("Web search is globally disabled")

        start_time = asyncio.get_event_loop().time()

        # Build SearXNG query parameters
        query_params = {
            "q": params.query,
            "format": "json",
            "categories": ",".join(params.categories),
        }

        if params.language and params.language != "auto":
            query_params["language"] = params.language

        if params.time_range:
            query_params["time_range"] = params.time_range

        # Perform search
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_ms / 1000)
        ) as client:
            response = await client.get(
                f"{self.searxng_url}/search",
                params=query_params
            )
            response.raise_for_status()
            data = response.json()

        # Parse results
        results = []
        raw_results = data.get("results", [])

        for item in raw_results[:min(params.num_results, self.max_results)]:
            result = SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source=item.get("engine", None),
                published_date=item.get("publishedDate", None),
                thumbnail_url=item.get("thumbnail", None)
            )
            results.append(result)

        search_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        return SearchResponse(
            results=results,
            query=params.query,
            total_results=len(results),
            search_time_ms=search_time_ms,
            suggestions=data.get("suggestions", [])
        )

    def get_tool_definition(self) -> Dict[str, Any]:
        """Get MCP tool definition for web search."""
        return {
            "name": "web_search",
            "description": "Search the web for information. Returns relevant web pages with titles, URLs, and snippets.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (1-50)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code (e.g., 'en', 'zh')",
                        "default": "auto"
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Time range filter",
                        "enum": ["day", "week", "month", "year"]
                    }
                },
                "required": ["query"]
            }
        }


# =============================================================================
# MCP Server Handler
# =============================================================================

class WebSearchMCPServer:
    """
    MCP server implementation for web search.

    Handles MCP protocol messages for the web search tool.
    """

    def __init__(self):
        self.tool = WebSearchTool()
        self.name = "web_search"
        self.version = "1.0.0"

    def get_server_info(self) -> Dict[str, Any]:
        """Get MCP server info."""
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": {
                "tools": {
                    "listChanged": False
                }
            }
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        if not self.tool.is_enabled():
            return []
        return [self.tool.get_tool_definition()]

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call a tool.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            MCP content response
        """
        if name != "web_search":
            return {
                "content": [{
                    "type": "text",
                    "text": f"Unknown tool: {name}"
                }],
                "isError": True
            }

        if not self.tool.is_enabled():
            return {
                "content": [{
                    "type": "text",
                    "text": "Web search is disabled"
                }],
                "isError": True
            }

        try:
            params = SearchParams(**arguments)
            result = await self.tool.search(params)

            # Format results for LLM consumption
            formatted_results = []
            for i, r in enumerate(result.results, 1):
                formatted_results.append(
                    f"{i}. **{r.title}**\n"
                    f"   URL: {r.url}\n"
                    f"   {r.snippet}\n"
                )

            text_content = f"Search results for: \"{result.query}\"\n\n"
            text_content += "\n".join(formatted_results)

            if result.suggestions:
                text_content += f"\n\nRelated searches: {', '.join(result.suggestions[:5])}"

            return {
                "content": [{
                    "type": "text",
                    "text": text_content
                }]
            }

        except Exception as e:
            logger.error(f"Web search error: {e}")
            return {
                "content": [{
                    "type": "text",
                    "text": f"Search failed: {str(e)}"
                }],
                "isError": True
            }


# =============================================================================
# FastAPI Router for MCP Server
# =============================================================================

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/mcp/web-search", tags=["mcp-web-search"])

# Global server instance
_server = WebSearchMCPServer()


@router.get("/info")
async def server_info():
    """Get MCP server information."""
    return _server.get_server_info()


@router.post("/tools/list")
async def list_tools():
    """List available tools."""
    return {"tools": _server.list_tools()}


@router.post("/tools/call")
async def call_tool(request: Request):
    """Call a tool."""
    data = await request.json()
    params = data.get("params", {})
    name = params.get("name")
    arguments = params.get("arguments", {})

    if not name:
        raise HTTPException(status_code=400, detail="Missing tool name")

    result = await _server.call_tool(name, arguments)
    return result


# =============================================================================
# Standalone Direct Integration (without MCP)
# =============================================================================

async def perform_web_search(
    query: str,
    num_results: int = 10,
    language: str = "auto",
    time_range: Optional[str] = None
) -> SearchResponse:
    """
    Perform a web search directly (without MCP).

    This function can be used when direct integration is preferred
    over the MCP protocol.
    """
    tool = WebSearchTool()
    params = SearchParams(
        query=query,
        num_results=num_results,
        language=language,
        time_range=time_range
    )
    return await tool.search(params)
