# Chat Console Module

The Chat Console module provides a ChatGPT-like chat interface with support for multiple AI model providers, MCP (Model Context Protocol) tools, and file attachments with RAG (Retrieval Augmented Generation).

## Features

- **Conversation Management**: Create, rename, delete, pin, and search conversations
- **Multi-Model Support**: Configure multiple model providers (internal gateway, OpenAI, custom deployments)
- **Streaming Responses**: Real-time streaming of AI responses using SSE
- **File Attachments**: Upload documents for context-aware responses with RAG
- **MCP Tools**: Integrated web search and document search tools
- **Public Apps**: Create shareable chat interfaces with token-based authentication

## Architecture

### Backend Components

```
app/
├── chat/
│   ├── api/
│   │   ├── admin.py      # Admin API endpoints
│   │   ├── public.py     # Public API endpoints
│   │   └── playground.py # Playground API endpoints
│   ├── services/
│   │   ├── mcp_client.py      # MCP client manager
│   │   ├── openai_client.py   # OpenAI-compatible client
│   │   ├── conversations.py   # Conversation service
│   │   └── uploads.py         # File upload service
│   └── tools/
├── mcp_servers/
│   ├── web_search_server/    # Web search MCP server
│   └── docs_server/          # Document search MCP server
└── models/
    └── chat.py               # Database models
```

### Frontend Components

```
src/features/chat/
├── api/
│   └── chatClient.ts         # API client
├── components/
│   ├── ChatThread.tsx        # Message display
│   ├── Composer.tsx          # Message input
│   ├── ConversationList.tsx  # Sidebar list
│   ├── ModelSelector.tsx     # Model dropdown
│   └── ModelProfileSettings.tsx # Settings modal
└── pages/
    └── ChatPage.tsx          # Main chat page
```

## Database Schema

### Model Profiles
Stores configuration for AI model providers.

```sql
CREATE TABLE chat_model_profiles (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    base_url VARCHAR(500) NOT NULL,
    encrypted_api_key TEXT,
    default_model VARCHAR(100),
    available_models JSONB DEFAULT '[]',
    capabilities JSONB DEFAULT '["chat"]',
    timeout_ms INTEGER DEFAULT 60000,
    enabled BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Conversations
Stores chat conversation metadata.

```sql
CREATE TABLE chat_conversations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    title VARCHAR(200) DEFAULT 'New Conversation',
    pinned BOOLEAN DEFAULT false,
    model_profile_id UUID REFERENCES chat_model_profiles(id),
    model VARCHAR(100),
    settings JSONB DEFAULT '{}',
    message_count INTEGER DEFAULT 0,
    last_message_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Messages
Stores individual messages in conversations.

```sql
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id),
    role chat_message_role NOT NULL, -- user, assistant, tool, system
    content JSONB NOT NULL,
    model VARCHAR(100),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoints

### Admin Endpoints (require session authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chat/model-profiles` | List model profiles |
| POST | `/api/chat/model-profiles` | Create model profile |
| PATCH | `/api/chat/model-profiles/{id}` | Update model profile |
| DELETE | `/api/chat/model-profiles/{id}` | Delete model profile |
| GET | `/api/chat/conversations` | List conversations |
| POST | `/api/chat/conversations` | Create conversation |
| GET | `/api/chat/conversations/{id}` | Get conversation details |
| PATCH | `/api/chat/conversations/{id}` | Update conversation |
| DELETE | `/api/chat/conversations/{id}` | Delete conversation |
| GET | `/api/chat/conversations/{id}/messages` | Get messages |
| POST | `/api/chat/conversations/{id}/send` | Send message (SSE) |
| POST | `/api/chat/conversations/{id}/regenerate/{msg_id}` | Regenerate message |
| POST | `/api/chat/conversations/{id}/upload` | Upload file |
| GET | `/api/chat/conversations/{id}/attachments` | List attachments |
| DELETE | `/api/chat/attachments/{id}` | Delete attachment |

### Public Endpoints (require app token)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/public/apps/{app_id}/info` | Get app info |
| POST | `/api/public/apps/{app_id}/send` | Send message (SSE) |
| POST | `/api/public/apps/{app_id}/upload` | Upload file |
| POST | `/api/public/apps/{app_id}/chat/completions` | OpenAI-compatible endpoint |

## Configuration

Add the following to your `.env` file:

```bash
# Chat Settings
CHAT_upload_max_file_size_mb=50
CHAT_chunk_size=500
CHAT_chunk_overlap=50
CHAT_embedding_model=text-embedding-3-small
CHAT_embedding_dim=1536
CHAT_stream_chunk_size=1024
CHAT_rate_limit_per_minute=60

# MCP Settings
MCP_web_search_enabled=true
MCP_web_search_searxng_url=http://localhost:8888
MCP_web_search_timeout_ms=10000
MCP_web_search_max_results=5
```

## Usage Examples

### Creating a Model Profile

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/chat/model-profiles",
    json={
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-...",
        "default_model": "gpt-4",
        "available_models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
        "capabilities": ["chat", "embedding", "image"],
        "is_default": True
    },
    cookies={"session_id": "..."}
)
```

### Sending a Message with Streaming

```typescript
const eventSource = new EventSource(
  `/api/chat/conversations/${conversationId}/send`,
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: 'Hello, how are you?' })
  }
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'delta') {
    console.log(data.data.content);
  }
};
```

### Using the OpenAI-Compatible API

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/api/public/apps/{app_id}",
    api_key="your-app-token"
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content, end="")
```

## Security Considerations

- API keys are encrypted at rest using Fernet encryption
- Session-based authentication for admin endpoints
- Token-based authentication for public endpoints
- Rate limiting per user/app
- File upload size limits and type validation
- XSS prevention in rendered content
