"""
File Upload and Document Indexing Service.

This module handles:
- File uploads to MinIO
- Text extraction from documents (PDF, DOCX, etc.)
- Document chunking for RAG
- Embedding generation and storage

References:
- MinIO Python SDK: https://min.io/docs/minio/linux/developers/python/API.html
"""

import asyncio
import hashlib
import io
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from minio import Minio
from minio.error import S3Error
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chat import (
    ChatAttachment,
    ChatDocChunk,
    ChatDocEmbedding,
    ChatConversation,
    ChatModelProfile,
)
from app.chat.services.openai_client import ModelProfileService

logger = logging.getLogger(__name__)


# =============================================================================
# Text Extractors
# =============================================================================

class TextExtractor:
    """Base class for text extractors."""

    async def extract(self, content: bytes, mime_type: str) -> str:
        """Extract text from content."""
        raise NotImplementedError


class PlainTextExtractor(TextExtractor):
    """Extract text from plain text files."""

    async def extract(self, content: bytes, mime_type: str) -> str:
        encodings = ["utf-8", "latin-1", "cp1252"]
        for encoding in encodings:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="ignore")


class PDFExtractor(TextExtractor):
    """Extract text from PDF files."""

    async def extract(self, content: bytes, mime_type: str) -> str:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content))
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            return "\n\n".join(text_parts)
        except ImportError:
            logger.warning("pypdf not installed, PDF extraction disabled")
            return ""
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""


class DocxExtractor(TextExtractor):
    """Extract text from DOCX files."""

    async def extract(self, content: bytes, mime_type: str) -> str:
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            text_parts = []
            for para in doc.paragraphs:
                text_parts.append(para.text)
            return "\n".join(text_parts)
        except ImportError:
            logger.warning("python-docx not installed, DOCX extraction disabled")
            return ""
        except Exception as e:
            logger.error(f"DOCX extraction error: {e}")
            return ""


class HTMLExtractor(TextExtractor):
    """Extract text from HTML files."""

    async def extract(self, content: bytes, mime_type: str) -> str:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            return soup.get_text(separator="\n", strip=True)
        except ImportError:
            logger.warning("beautifulsoup4 not installed, HTML extraction disabled")
            return content.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"HTML extraction error: {e}")
            return ""


def get_extractor(mime_type: str) -> TextExtractor:
    """Get appropriate extractor for mime type."""
    extractors = {
        "text/plain": PlainTextExtractor(),
        "text/markdown": PlainTextExtractor(),
        "text/csv": PlainTextExtractor(),
        "application/json": PlainTextExtractor(),
        "application/xml": PlainTextExtractor(),
        "text/xml": PlainTextExtractor(),
        "text/html": HTMLExtractor(),
        "application/pdf": PDFExtractor(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxExtractor(),
    }

    # Check for code files
    code_types = ["text/x-python", "text/javascript", "text/x-java", "text/x-c", "text/x-go"]
    for ct in code_types:
        extractors[ct] = PlainTextExtractor()

    return extractors.get(mime_type, PlainTextExtractor())


# =============================================================================
# Document Chunker
# =============================================================================

class DocumentChunker:
    """Split documents into chunks for embedding."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def split(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into chunks.

        Returns list of dicts with:
        - content: chunk text
        - start_char: start position
        - end_char: end position
        - char_count: number of characters
        """
        if not text:
            return []

        chunks = self._split_text(text, self.separators)

        result = []
        current_pos = 0

        for i, chunk in enumerate(chunks):
            # Find actual position in original text
            chunk_start = text.find(chunk, current_pos)
            if chunk_start == -1:
                chunk_start = current_pos

            result.append({
                "content": chunk,
                "start_char": chunk_start,
                "end_char": chunk_start + len(chunk),
                "char_count": len(chunk),
                "chunk_index": i
            })

            current_pos = chunk_start + len(chunk) - self.chunk_overlap

        return result

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text by separators."""
        final_chunks = []
        separator = separators[-1]
        new_separators = []

        for i, sep in enumerate(separators):
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1:]
                break

        splits = text.split(separator) if separator else list(text)
        good_splits = []
        separator_to_add = separator if separator else ""

        for s in splits:
            if len(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if good_splits:
                    merged = self._merge_splits(good_splits, separator_to_add)
                    final_chunks.extend(merged)
                    good_splits = []

                if not new_separators:
                    final_chunks.append(s)
                else:
                    other_chunks = self._split_text(s, new_separators)
                    final_chunks.extend(other_chunks)

        if good_splits:
            merged = self._merge_splits(good_splits, separator_to_add)
            final_chunks.extend(merged)

        return final_chunks

    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        """Merge splits into chunks respecting size limits."""
        merged = []
        current = []
        current_len = 0

        for s in splits:
            s_len = len(s)
            sep_len = len(separator) if current else 0

            if current_len + s_len + sep_len > self.chunk_size:
                if current:
                    merged.append(separator.join(current))
                    # Keep overlap
                    while current_len > self.chunk_overlap and current:
                        current.pop(0)
                        current_len = sum(len(x) for x in current) + len(separator) * (len(current) - 1)

            current.append(s)
            current_len += s_len + sep_len

        if current:
            merged.append(separator.join(current))

        return merged


# =============================================================================
# Upload Service
# =============================================================================

class UploadService:
    """
    Service for handling file uploads and document indexing.

    Handles:
    - File upload to MinIO
    - Text extraction
    - Document chunking
    - Embedding generation
    """

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self._minio_client: Optional[Minio] = None

    def _get_minio_client(self) -> Minio:
        """Get or create MinIO client."""
        if self._minio_client is None:
            self._minio_client = Minio(
                endpoint=settings.minio.endpoint,
                access_key=settings.minio.access_key,
                secret_key=settings.minio.secret_key,
                secure=settings.minio.secure
            )
        return self._minio_client

    async def upload_file(
        self,
        conversation_id: UUID,
        file_name: str,
        content: bytes,
        mime_type: str,
        user_id: Optional[UUID] = None,
        usage_mode: str = "retrieval"
    ) -> ChatAttachment:
        """
        Upload a file and create attachment record.

        Args:
            conversation_id: Target conversation
            file_name: Original file name
            content: File content
            mime_type: MIME type
            user_id: Uploading user
            usage_mode: "retrieval", "direct", or "both"

        Returns:
            Created ChatAttachment
        """
        # Validate file
        self._validate_file(file_name, content, mime_type)

        # Calculate hash
        sha256 = hashlib.sha256(content).hexdigest()

        # Generate storage key
        bucket = settings.chat.attachments_bucket
        key = f"{self.tenant_id}/{conversation_id}/{uuid4()}/{file_name}"

        # Upload to MinIO
        client = self._get_minio_client()

        # Ensure bucket exists
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

        # Upload file
        client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=io.BytesIO(content),
            length=len(content),
            content_type=mime_type
        )

        # Create attachment record
        attachment = ChatAttachment(
            conversation_id=conversation_id,
            file_name=file_name,
            original_name=file_name,
            mime_type=mime_type,
            size_bytes=len(content),
            minio_bucket=bucket,
            minio_key=key,
            sha256=sha256,
            usage_mode=usage_mode,
            uploaded_by=user_id,
            extraction_status="pending"
        )

        self.db.add(attachment)
        await self.db.commit()
        await self.db.refresh(attachment)

        return attachment

    def _validate_file(self, file_name: str, content: bytes, mime_type: str) -> None:
        """Validate file against configured limits."""
        # Check file size
        max_size = settings.chat.upload_max_file_size_mb * 1024 * 1024
        if len(content) > max_size:
            raise ValueError(f"File too large. Maximum size is {settings.chat.upload_max_file_size_mb}MB")

        # Check extension
        ext = os.path.splitext(file_name)[1].lower()
        if ext and ext not in settings.chat.allowed_extensions_list:
            raise ValueError(f"File type not allowed: {ext}")

    async def process_document(
        self,
        attachment_id: UUID,
        embedding_profile_id: Optional[UUID] = None
    ) -> None:
        """
        Process a document for RAG.

        Steps:
        1. Extract text
        2. Split into chunks
        3. Generate embeddings
        4. Store in database

        Args:
            attachment_id: The attachment to process
            embedding_profile_id: Model profile for embeddings
        """
        # Get attachment
        stmt = select(ChatAttachment).where(ChatAttachment.id == attachment_id)
        result = await self.db.execute(stmt)
        attachment = result.scalar_one_or_none()

        if not attachment:
            raise ValueError("Attachment not found")

        try:
            # Update status
            attachment.extraction_status = "processing"
            await self.db.commit()

            # Download file from MinIO
            client = self._get_minio_client()
            response = client.get_object(attachment.minio_bucket, attachment.minio_key)
            content = response.read()
            response.close()

            # Extract text
            extractor = get_extractor(attachment.mime_type)
            text = await extractor.extract(content, attachment.mime_type)

            if not text:
                attachment.extraction_status = "empty"
                attachment.extraction_error = "No text content extracted"
                await self.db.commit()
                return

            # Chunk the document
            chunker = DocumentChunker(
                chunk_size=settings.chat.chunk_size,
                chunk_overlap=settings.chat.chunk_overlap
            )
            chunks = chunker.split(text)

            # Limit chunks
            if len(chunks) > settings.chat.max_chunks_per_document:
                chunks = chunks[:settings.chat.max_chunks_per_document]

            # Save chunks
            for chunk_data in chunks:
                chunk = ChatDocChunk(
                    attachment_id=attachment_id,
                    chunk_index=chunk_data["chunk_index"],
                    content=chunk_data["content"],
                    char_count=chunk_data["char_count"],
                    start_char=chunk_data["start_char"],
                    end_char=chunk_data["end_char"]
                )
                self.db.add(chunk)

            attachment.chunk_count = len(chunks)
            attachment.extraction_status = "completed"
            attachment.embedding_status = "pending"
            await self.db.commit()

            # Generate embeddings if profile provided
            if embedding_profile_id:
                await self.generate_embeddings(attachment_id, embedding_profile_id)

        except Exception as e:
            logger.error(f"Document processing error: {e}")
            attachment.extraction_status = "error"
            attachment.extraction_error = str(e)
            await self.db.commit()
            raise

    async def generate_embeddings(
        self,
        attachment_id: UUID,
        profile_id: UUID
    ) -> None:
        """
        Generate embeddings for document chunks.

        Args:
            attachment_id: The attachment with chunks
            profile_id: Model profile for embedding generation
        """
        # Get chunks
        chunks_stmt = select(ChatDocChunk).where(
            ChatDocChunk.attachment_id == attachment_id
        ).order_by(ChatDocChunk.chunk_index)

        result = await self.db.execute(chunks_stmt)
        chunks = list(result.scalars().all())

        if not chunks:
            return

        # Get embedding client
        profile_service = ModelProfileService(self.db, self.tenant_id)
        client = await profile_service.create_client(profile_id=profile_id)

        try:
            # Update attachment status
            await self.db.execute(
                update(ChatAttachment)
                .where(ChatAttachment.id == attachment_id)
                .values(embedding_status="processing")
            )
            await self.db.commit()

            # Process in batches
            batch_size = settings.chat.embedding_batch_size
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                texts = [c.content for c in batch]

                # Get embeddings
                embeddings = await client.embeddings(texts)

                # Save embeddings
                for chunk, embedding in zip(batch, embeddings):
                    emb = ChatDocEmbedding(
                        chunk_id=chunk.id,
                        embedding=embedding,
                        model_profile_id=profile_id,
                        embedding_model=client.model_profile.default_model,
                        embedding_dimensions=len(embedding)
                    )
                    self.db.add(emb)

                await self.db.commit()

            # Update attachment status
            await self.db.execute(
                update(ChatAttachment)
                .where(ChatAttachment.id == attachment_id)
                .values(embedding_status="completed")
            )
            await self.db.commit()

        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            await self.db.execute(
                update(ChatAttachment)
                .where(ChatAttachment.id == attachment_id)
                .values(embedding_status="error")
            )
            await self.db.commit()
            raise

        finally:
            await client.close()

    async def get_file_content(self, attachment_id: UUID) -> Tuple[bytes, str, str]:
        """
        Get file content from MinIO.

        Returns:
            Tuple of (content, file_name, mime_type)
        """
        stmt = select(ChatAttachment).where(ChatAttachment.id == attachment_id)
        result = await self.db.execute(stmt)
        attachment = result.scalar_one_or_none()

        if not attachment:
            raise ValueError("Attachment not found")

        client = self._get_minio_client()
        response = client.get_object(attachment.minio_bucket, attachment.minio_key)
        content = response.read()
        response.close()

        return content, attachment.file_name, attachment.mime_type

    async def delete_file(self, attachment_id: UUID) -> bool:
        """Delete a file and all associated data."""
        stmt = select(ChatAttachment).where(ChatAttachment.id == attachment_id)
        result = await self.db.execute(stmt)
        attachment = result.scalar_one_or_none()

        if not attachment:
            return False

        # Delete from MinIO
        try:
            client = self._get_minio_client()
            client.remove_object(attachment.minio_bucket, attachment.minio_key)
        except S3Error as e:
            logger.warning(f"Failed to delete from MinIO: {e}")

        # Delete from database (cascades to chunks and embeddings)
        await self.db.delete(attachment)
        await self.db.commit()

        return True


# =============================================================================
# Factory Function
# =============================================================================

def create_upload_service(db: AsyncSession, tenant_id: UUID) -> UploadService:
    """Create an upload service instance."""
    return UploadService(db, tenant_id)
