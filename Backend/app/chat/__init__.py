"""
Chat Module.

This module provides ChatGPT-like chat functionality with:
- Conversation management
- Streaming chat completions
- File upload and document search (RAG)
- MCP tool integration
- Public chat apps
"""

from app.chat.api.admin import router as admin_router
from app.chat.api.public import router as public_router

__all__ = ["admin_router", "public_router"]
