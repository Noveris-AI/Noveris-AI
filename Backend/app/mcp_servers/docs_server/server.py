"""
Document Search MCP Server.

This module implements an MCP server that provides document search capabilities
for the Chat module's RAG (Retrieval Augmented Generation) feature.

Features:
- List uploaded files in a conversation
- Search document chunks using semantic similarity
- Retrieve specific chunks with full content
- Citation formatting for LLM consumption

This server is purely internal and does not make external network requests.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import (
    ChatAttachment,
    ChatDocChunk,
    ChatDocEmbedding,
    ChatConversation,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Schemas
# =============================================================================

class FileInfo(BaseModel):
    """Information about an uploaded file."""
    file_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    chunk_count: int
    extraction_status: str
    created_at: str


class ChunkResult(BaseModel):
    """A document chunk search result."""
    chunk_id: str
    file_id: str
    file_name: str
    chunk_index: int
    content: str
    score: float
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = {}


class SearchDocsResponse(BaseModel):
    """Response from document search."""
    results: List[ChunkResult]
    query: str
    total_results: int


# =============================================================================
# Document Search Service
# =============================================================================

class DocsSearchService:
    """
    Document search service using vector similarity.

    This service searches through uploaded documents in a conversation
    using semantic similarity based on embeddings.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_files(
        self,
        conversation_id: UUID
    ) -> List[FileInfo]:
        """
        List all files uploaded to a conversation.

        Args:
            conversation_id: The conversation UUID

        Returns:
            List of file information
        """
        stmt = select(ChatAttachment).where(
            ChatAttachment.conversation_id == conversation_id
        ).order_by(ChatAttachment.created_at.desc())

        result = await self.db.execute(stmt)
        attachments = result.scalars().all()

        files = []
        for att in attachments:
            files.append(FileInfo(
                file_id=str(att.id),
                file_name=att.file_name,
                mime_type=att.mime_type,
                size_bytes=att.size_bytes,
                chunk_count=att.chunk_count,
                extraction_status=att.extraction_status,
                created_at=att.created_at.isoformat()
            ))

        return files

    async def search_docs(
        self,
        conversation_id: UUID,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0
    ) -> List[ChunkResult]:
        """
        Search documents using vector similarity.

        Args:
            conversation_id: The conversation UUID
            query_embedding: Query embedding vector
            top_k: Number of top results to return
            score_threshold: Minimum similarity score

        Returns:
            List of matching chunks with scores
        """
        # Get all attachments for the conversation
        attachments_stmt = select(ChatAttachment.id).where(
            ChatAttachment.conversation_id == conversation_id,
            ChatAttachment.embedding_status == "completed"
        )
        attachments_result = await self.db.execute(attachments_stmt)
        attachment_ids = [row[0] for row in attachments_result.fetchall()]

        if not attachment_ids:
            return []

        # Get all chunks for these attachments
        chunks_stmt = select(ChatDocChunk).where(
            ChatDocChunk.attachment_id.in_(attachment_ids)
        )
        chunks_result = await self.db.execute(chunks_stmt)
        chunks = {str(c.id): c for c in chunks_result.scalars().all()}

        if not chunks:
            return []

        # Get embeddings for all chunks
        embeddings_stmt = select(ChatDocEmbedding).where(
            ChatDocEmbedding.chunk_id.in_([UUID(cid) for cid in chunks.keys()])
        )
        embeddings_result = await self.db.execute(embeddings_stmt)
        embeddings = embeddings_result.scalars().all()

        # Calculate cosine similarity
        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)

        if query_norm == 0:
            return []

        scored_chunks = []
        for emb in embeddings:
            if emb.embedding is None:
                continue

            chunk_vec = np.array(emb.embedding)
            chunk_norm = np.linalg.norm(chunk_vec)

            if chunk_norm == 0:
                continue

            # Cosine similarity
            similarity = np.dot(query_vec, chunk_vec) / (query_norm * chunk_norm)

            if similarity >= score_threshold:
                chunk = chunks.get(str(emb.chunk_id))
                if chunk:
                    scored_chunks.append((chunk, float(similarity)))

        # Sort by score and take top_k
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        top_chunks = scored_chunks[:top_k]

        # Get attachment info for results
        attachment_ids_needed = list(set(str(c.attachment_id) for c, _ in top_chunks))
        if attachment_ids_needed:
            att_stmt = select(ChatAttachment).where(
                ChatAttachment.id.in_([UUID(aid) for aid in attachment_ids_needed])
            )
            att_result = await self.db.execute(att_stmt)
            attachments = {str(a.id): a for a in att_result.scalars().all()}
        else:
            attachments = {}

        # Build results
        results = []
        for chunk, score in top_chunks:
            att = attachments.get(str(chunk.attachment_id))
            results.append(ChunkResult(
                chunk_id=str(chunk.id),
                file_id=str(chunk.attachment_id),
                file_name=att.file_name if att else "Unknown",
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=score,
                page_number=chunk.page_number,
                metadata=chunk.chunk_metadata or {}
            ))

        return results

    async def get_chunk(
        self,
        file_id: UUID,
        chunk_index: int
    ) -> Optional[ChunkResult]:
        """
        Get a specific chunk by file ID and chunk index.

        Args:
            file_id: The file (attachment) UUID
            chunk_index: The chunk index within the file

        Returns:
            Chunk content if found
        """
        stmt = select(ChatDocChunk).where(
            ChatDocChunk.attachment_id == file_id,
            ChatDocChunk.chunk_index == chunk_index
        )
        result = await self.db.execute(stmt)
        chunk = result.scalar_one_or_none()

        if not chunk:
            return None

        # Get attachment info
        att_stmt = select(ChatAttachment).where(ChatAttachment.id == file_id)
        att_result = await self.db.execute(att_stmt)
        att = att_result.scalar_one_or_none()

        return ChunkResult(
            chunk_id=str(chunk.id),
            file_id=str(chunk.attachment_id),
            file_name=att.file_name if att else "Unknown",
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=1.0,
            page_number=chunk.page_number,
            metadata=chunk.chunk_metadata or {}
        )


# =============================================================================
# MCP Server Handler
# =============================================================================

class DocsMCPServer:
    """
    MCP server implementation for document search.

    Handles MCP protocol messages for document-related tools.
    """

    def __init__(self, db: AsyncSession):
        self.service = DocsSearchService(db)
        self.name = "docs"
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
        return [
            {
                "name": "list_files",
                "description": "List all files uploaded to the current conversation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "conversation_id": {
                            "type": "string",
                            "description": "The conversation UUID"
                        }
                    },
                    "required": ["conversation_id"]
                }
            },
            {
                "name": "search_docs",
                "description": "Search through uploaded documents for relevant content. Returns chunks with citations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "conversation_id": {
                            "type": "string",
                            "description": "The conversation UUID"
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 20
                        }
                    },
                    "required": ["conversation_id", "query"]
                }
            },
            {
                "name": "get_chunk",
                "description": "Get the full content of a specific document chunk",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "The file UUID"
                        },
                        "chunk_index": {
                            "type": "integer",
                            "description": "The chunk index within the file"
                        }
                    },
                    "required": ["file_id", "chunk_index"]
                }
            }
        ]

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        get_embedding_fn: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Call a tool.

        Args:
            name: Tool name
            arguments: Tool arguments
            get_embedding_fn: Optional function to get embeddings for queries

        Returns:
            MCP content response
        """
        try:
            if name == "list_files":
                conversation_id = UUID(arguments["conversation_id"])
                files = await self.service.list_files(conversation_id)

                if not files:
                    return {
                        "content": [{
                            "type": "text",
                            "text": "No files have been uploaded to this conversation."
                        }]
                    }

                text = "Uploaded files:\n\n"
                for f in files:
                    text += f"- **{f.file_name}** ({f.mime_type})\n"
                    text += f"  Size: {f.size_bytes:,} bytes, Chunks: {f.chunk_count}\n"
                    text += f"  Status: {f.extraction_status}\n\n"

                return {
                    "content": [{
                        "type": "text",
                        "text": text
                    }]
                }

            elif name == "search_docs":
                conversation_id = UUID(arguments["conversation_id"])
                query = arguments["query"]
                top_k = arguments.get("top_k", 5)

                # Get query embedding
                if get_embedding_fn is None:
                    return {
                        "content": [{
                            "type": "text",
                            "text": "Document search requires embedding function"
                        }],
                        "isError": True
                    }

                query_embedding = await get_embedding_fn(query)
                results = await self.service.search_docs(
                    conversation_id, query_embedding, top_k
                )

                if not results:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"No relevant content found for: \"{query}\""
                        }]
                    }

                text = f"Search results for: \"{query}\"\n\n"
                for i, r in enumerate(results, 1):
                    text += f"**[{i}] {r.file_name}** (chunk {r.chunk_index + 1})"
                    if r.page_number:
                        text += f" - Page {r.page_number}"
                    text += f" [score: {r.score:.3f}]\n"
                    text += f"{r.content[:500]}{'...' if len(r.content) > 500 else ''}\n\n"

                return {
                    "content": [{
                        "type": "text",
                        "text": text
                    }]
                }

            elif name == "get_chunk":
                file_id = UUID(arguments["file_id"])
                chunk_index = arguments["chunk_index"]

                chunk = await self.service.get_chunk(file_id, chunk_index)

                if not chunk:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Chunk not found: file={file_id}, index={chunk_index}"
                        }],
                        "isError": True
                    }

                text = f"**{chunk.file_name}** - Chunk {chunk.chunk_index + 1}"
                if chunk.page_number:
                    text += f" (Page {chunk.page_number})"
                text += f"\n\n{chunk.content}"

                return {
                    "content": [{
                        "type": "text",
                        "text": text
                    }]
                }

            else:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Unknown tool: {name}"
                    }],
                    "isError": True
                }

        except Exception as e:
            logger.error(f"Docs tool error: {e}")
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error: {str(e)}"
                }],
                "isError": True
            }


# =============================================================================
# Factory Function
# =============================================================================

def create_docs_mcp_server(db: AsyncSession) -> DocsMCPServer:
    """Create a docs MCP server instance."""
    return DocsMCPServer(db)
