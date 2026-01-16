# Public Chat Apps

Public Chat Apps allow you to create shareable chat interfaces that can be embedded in external applications or websites. Each app has its own authentication token and can be configured with custom settings.

## Overview

Public apps provide:

- **Token-based authentication** for API access
- **OpenAI-compatible API** for easy integration
- **Rate limiting** per app
- **Custom system prompts** and model settings
- **File upload support** for RAG

## Creating a Public App

### Via Admin API

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/chat/public-apps",
    json={
        "name": "Customer Support Bot",
        "description": "AI-powered customer support",
        "model_profile_id": "uuid-of-profile",
        "model": "gpt-4",
        "settings": {
            "system_prompt": "You are a helpful customer support assistant.",
            "temperature": 0.7,
            "max_tokens": 2000,
            "enable_web_search": False
        },
        "rate_limit_per_minute": 30,
        "allowed_origins": ["https://myapp.com"]
    },
    cookies={"session_id": "..."}
)

app = response.json()
print(f"App Token: {app['token']}")  # Save this token securely!
```

### Configuration Options

| Field | Type | Description |
|-------|------|-------------|
| name | string | Display name for the app |
| description | string | Optional description |
| model_profile_id | UUID | Model provider to use |
| model | string | Specific model (e.g., gpt-4) |
| settings | object | Custom app settings |
| rate_limit_per_minute | integer | API rate limit |
| allowed_origins | array | CORS allowed origins |
| expires_at | datetime | Optional expiration date |

### Settings Object

```json
{
  "system_prompt": "Custom system prompt...",
  "temperature": 0.7,
  "max_tokens": 2000,
  "top_p": 1.0,
  "presence_penalty": 0.0,
  "frequency_penalty": 0.0,
  "enable_web_search": true,
  "enable_file_upload": true,
  "max_file_size_mb": 10
}
```

## Using the Public API

### Authentication

Include the app token in the Authorization header:

```
Authorization: Bearer <app-token>
```

### Send Message (SSE Streaming)

```bash
curl -X POST "https://api.example.com/api/public/apps/{app_id}/send" \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello, I need help with my order."}'
```

**Response (Server-Sent Events):**

```
data: {"type": "start", "data": {"message_id": "uuid"}}

data: {"type": "delta", "data": {"content": "Hello"}}

data: {"type": "delta", "data": {"content": "! How"}}

data: {"type": "delta", "data": {"content": " can I help"}}

data: {"type": "done", "data": {"prompt_tokens": 50, "completion_tokens": 120}}

data: [DONE]
```

### OpenAI-Compatible Endpoint

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.example.com/api/public/apps/{app_id}",
    api_key="your-app-token"
)

# Non-streaming
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "What's the status of order #12345?"}
    ]
)
print(response.choices[0].message.content)

# Streaming
stream = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "What's the status of order #12345?"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### File Upload

```bash
curl -X POST "https://api.example.com/api/public/apps/{app_id}/upload" \
  -H "Authorization: Bearer $APP_TOKEN" \
  -F "file=@document.pdf" \
  -F "usage_mode=retrieval"
```

**Response:**

```json
{
  "id": "attachment-uuid",
  "file_name": "document.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 102400,
  "extraction_status": "processing",
  "embedding_status": "pending"
}
```

## Frontend Integration

### JavaScript SDK Example

```javascript
class PublicChatClient {
  constructor(appId, token, baseUrl = '') {
    this.appId = appId;
    this.token = token;
    this.baseUrl = baseUrl;
  }

  async sendMessage(content, onChunk) {
    const response = await fetch(
      `${this.baseUrl}/api/public/apps/${this.appId}/send`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data === '[DONE]') return;

          const event = JSON.parse(data);
          if (event.type === 'delta') {
            onChunk(event.data.content);
          }
        }
      }
    }
  }
}

// Usage
const chat = new PublicChatClient('app-id', 'app-token');
chat.sendMessage('Hello!', (chunk) => {
  console.log(chunk);
});
```

### React Component Example

```tsx
import { useState, useCallback } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

function PublicChat({ appId, token }: { appId: string; token: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isStreaming) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);

    const assistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      const response = await fetch(`/api/public/apps/${appId}/send`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: userMessage.content }),
      });

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;

            const event = JSON.parse(data);
            if (event.type === 'delta') {
              setMessages(prev => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                last.content += event.data.content;
                return updated;
              });
            }
          }
        }
      }
    } finally {
      setIsStreaming(false);
    }
  }, [appId, token, input, isStreaming]);

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
      </div>
      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          disabled={isStreaming}
        />
        <button onClick={sendMessage} disabled={isStreaming}>
          Send
        </button>
      </div>
    </div>
  );
}
```

## Rate Limiting

Public apps enforce rate limiting to prevent abuse:

- Default: 60 requests per minute
- Configurable per app
- Burst allowance: 10 requests

Rate limit headers:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 55
X-RateLimit-Reset: 1699999999
```

When rate limited, the API returns:

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Try again in 30 seconds."
  }
}
```

## Security Best Practices

1. **Token Storage**: Store app tokens securely (environment variables, secrets manager)
2. **CORS**: Configure `allowed_origins` to restrict access to trusted domains
3. **Expiration**: Set `expires_at` for temporary apps
4. **Rate Limits**: Configure appropriate limits for your use case
5. **Monitoring**: Monitor usage through the admin dashboard
6. **Rotation**: Rotate tokens periodically

## Managing Apps

### List Apps

```bash
curl -X GET "https://api.example.com/api/chat/public-apps" \
  -H "Cookie: session_id=..."
```

### Update App

```bash
curl -X PATCH "https://api.example.com/api/chat/public-apps/{app_id}" \
  -H "Cookie: session_id=..." \
  -H "Content-Type: application/json" \
  -d '{"rate_limit_per_minute": 100}'
```

### Regenerate Token

```bash
curl -X POST "https://api.example.com/api/chat/public-apps/{app_id}/regenerate-token" \
  -H "Cookie: session_id=..."
```

### Delete App

```bash
curl -X DELETE "https://api.example.com/api/chat/public-apps/{app_id}" \
  -H "Cookie: session_id=..."
```

## Metrics & Analytics

Track app usage through the analytics endpoints:

```bash
curl -X GET "https://api.example.com/api/chat/public-apps/{app_id}/analytics" \
  -H "Cookie: session_id=..." \
  -G -d "start_date=2024-01-01" -d "end_date=2024-01-31"
```

**Response:**

```json
{
  "total_requests": 15420,
  "total_tokens": 2500000,
  "unique_sessions": 850,
  "avg_response_time_ms": 1250,
  "error_rate": 0.02,
  "daily_breakdown": [
    {"date": "2024-01-01", "requests": 500, "tokens": 80000}
  ]
}
```
