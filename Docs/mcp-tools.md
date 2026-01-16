# MCP Tools Integration

This document describes the Model Context Protocol (MCP) integration for providing AI models with access to external tools and data sources.

## Overview

MCP enables AI models to access external capabilities through a standardized protocol. The Chat module includes two built-in MCP servers:

1. **Web Search Server**: Provides web search capabilities using SearXNG
2. **Docs Server**: Provides document search over uploaded files using vector similarity

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│   Chat Service  │────▶│  MCP Client Mgr  │
└─────────────────┘     └──────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Web Search    │     │ Docs Server   │     │ External MCP  │
│ MCP Server    │     │ MCP Server    │     │ Servers       │
└───────────────┘     └───────────────┘     └───────────────┘
        │                      │
        ▼                      ▼
┌───────────────┐     ┌───────────────┐
│   SearXNG     │     │   pgvector    │
└───────────────┘     └───────────────┘
```

## Web Search Server

### Tool: `web_search`

Performs web searches using SearXNG as the backend search engine.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| query | string | Yes | Search query |
| max_results | integer | No | Maximum results (default: 5) |
| language | string | No | Language filter (default: auto) |
| categories | array | No | Search categories (default: general) |

**Response:**

```json
{
  "results": [
    {
      "title": "Result Title",
      "url": "https://example.com/page",
      "content": "Snippet of the page content...",
      "engine": "google"
    }
  ],
  "suggestions": ["related search 1", "related search 2"]
}
```

### Configuration

```bash
# Enable web search
MCP_web_search_enabled=true

# SearXNG instance URL
MCP_web_search_searxng_url=http://localhost:8888

# Request timeout
MCP_web_search_timeout_ms=10000

# Max results per search
MCP_web_search_max_results=5
```

### SearXNG Setup

To enable web search, deploy a SearXNG instance:

```yaml
# docker-compose.yml
services:
  searxng:
    image: searxng/searxng:latest
    ports:
      - "8888:8080"
    volumes:
      - ./searxng:/etc/searxng:rw
    environment:
      - SEARXNG_BASE_URL=http://localhost:8888/
```

Configure SearXNG settings in `searxng/settings.yml`:

```yaml
search:
  formats:
    - html
    - json

outgoing:
  request_timeout: 5.0
  max_request_timeout: 15.0

server:
  limiter: false  # For internal use

engines:
  - name: google
    engine: google
    shortcut: g
    disabled: false
```

## Docs Server

### Tool: `search_docs`

Searches uploaded documents using vector similarity.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| query | string | Yes | Search query |
| conversation_id | string | Yes | Conversation context |
| top_k | integer | No | Number of results (default: 5) |
| threshold | float | No | Similarity threshold (default: 0.7) |

**Response:**

```json
{
  "chunks": [
    {
      "chunk_id": "uuid",
      "file_name": "document.pdf",
      "content": "Relevant text content...",
      "similarity": 0.89,
      "page_number": 3
    }
  ]
}
```

### Tool: `list_files`

Lists all uploaded files in a conversation.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| conversation_id | string | Yes | Conversation context |

**Response:**

```json
{
  "files": [
    {
      "id": "uuid",
      "file_name": "document.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 102400,
      "chunk_count": 15,
      "status": "ready"
    }
  ]
}
```

### Tool: `get_chunk`

Retrieves a specific document chunk.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| chunk_id | string | Yes | Chunk identifier |

**Response:**

```json
{
  "content": "Full chunk content...",
  "metadata": {
    "file_name": "document.pdf",
    "page_number": 3,
    "char_start": 1500,
    "char_end": 2000
  }
}
```

## External MCP Servers

The MCP Client Manager can connect to external MCP servers that implement the MCP protocol.

### Registering an External Server

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/chat/mcp-servers",
    json={
        "name": "Custom Tools",
        "url": "http://mcp-server:3000",
        "transport": "http",  # http, sse, or stdio
        "api_key": "optional-key",
        "enabled": True
    },
    cookies={"session_id": "..."}
)
```

### Supported Transports

| Transport | Description | Use Case |
|-----------|-------------|----------|
| `http` | HTTP POST requests | RESTful MCP servers |
| `sse` | Server-Sent Events | Streaming responses |
| `stdio` | Standard I/O | Local process servers |

## Tool Calling Flow

1. **User sends message** with potential tool triggers
2. **Chat service detects** tool calls in AI response
3. **MCP Client Manager** routes to appropriate server
4. **Tool executes** and returns results
5. **Results injected** into conversation context
6. **AI generates** final response with tool results

```python
# Tool call flow in conversation service
async def process_tool_calls(self, tool_calls: List[ToolCall]):
    results = []
    for call in tool_calls:
        server = await self.mcp_client.get_server_for_tool(call.name)
        result = await server.call_tool(call.name, call.arguments)
        results.append({
            "tool_call_id": call.id,
            "role": "tool",
            "content": json.dumps(result)
        })
    return results
```

## Rate Limiting

MCP tool calls are rate-limited per server:

```python
# Default rate limits
MCP_rate_limit_per_minute=30
MCP_rate_limit_burst=5
```

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1699999999
```

## Error Handling

Tool errors are returned in a standardized format:

```json
{
  "type": "tool_result",
  "tool_call_id": "call_123",
  "error": {
    "code": "TOOL_ERROR",
    "message": "Search service unavailable",
    "retryable": true
  }
}
```

Common error codes:

| Code | Description |
|------|-------------|
| `TOOL_NOT_FOUND` | Tool does not exist |
| `TOOL_ERROR` | Tool execution failed |
| `RATE_LIMITED` | Rate limit exceeded |
| `TIMEOUT` | Tool execution timed out |
| `AUTH_ERROR` | Authentication failed |

## Audit Logging

All MCP tool calls are logged for audit purposes:

```sql
CREATE TABLE chat_mcp_tool_calls (
    id UUID PRIMARY KEY,
    server_id UUID REFERENCES chat_mcp_servers(id),
    conversation_id UUID REFERENCES chat_conversations(id),
    tool_name VARCHAR(100) NOT NULL,
    arguments JSONB,
    result JSONB,
    error TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
