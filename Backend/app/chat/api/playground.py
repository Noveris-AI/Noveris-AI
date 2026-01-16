"""
Playground API Endpoints.

Provides endpoints for testing various model capabilities:
- Embeddings
- Reranking
- Image generation
- Audio transcription and TTS
"""

from typing import Optional, List, Any, Union
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import io

from app.core.database import get_db
from app.core.config import settings
from app.chat.services.openai_client import ModelProfileService
from app.models.chat import ChatModelProfile

router = APIRouter(prefix="/playground", tags=["playground"])


# Request/Response Models
class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str
    model_profile_id: Optional[str] = None


class EmbeddingData(BaseModel):
    object: str = "embedding"
    embedding: List[float]
    index: int


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: EmbeddingUsage


class RerankRequest(BaseModel):
    query: str
    documents: List[str]
    model: str
    model_profile_id: Optional[str] = None
    top_n: Optional[int] = 10


class RerankResult(BaseModel):
    index: int
    document: str
    relevance_score: float


class RerankResponse(BaseModel):
    model: str
    results: List[RerankResult]
    usage: Optional[dict] = None


class ImageGenerationRequest(BaseModel):
    prompt: str
    model: str
    model_profile_id: Optional[str] = None
    n: Optional[int] = 1
    size: Optional[str] = "1024x1024"
    quality: Optional[str] = "standard"
    style: Optional[str] = "vivid"


class ImageResult(BaseModel):
    url: Optional[str] = None
    b64_json: Optional[str] = None
    revised_prompt: Optional[str] = None


class ImageGenerationResponse(BaseModel):
    created: int
    data: List[ImageResult]


class TextToSpeechRequest(BaseModel):
    input: str
    model: str
    model_profile_id: Optional[str] = None
    voice: Optional[str] = "alloy"
    speed: Optional[float] = 1.0
    response_format: Optional[str] = "mp3"


class AudioTranscriptionResponse(BaseModel):
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    words: Optional[List[dict]] = None


async def get_profile_and_client(
    model_profile_id: Optional[str],
    session: AsyncSession,
) -> tuple[ChatModelProfile, httpx.AsyncClient, str]:
    """Get model profile and create HTTP client."""
    profile_service = ModelProfileService(session)

    if model_profile_id:
        profile = await profile_service.get_profile(model_profile_id)
    else:
        profile = await profile_service.get_default_profile()

    if not profile:
        raise HTTPException(status_code=404, detail="Model profile not found")

    api_key = await profile_service.decrypt_api_key(profile)

    client = httpx.AsyncClient(
        base_url=profile.base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=profile.timeout_ms / 1000,
    )

    return profile, client, api_key


@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embedding(
    request: EmbeddingRequest,
    session: AsyncSession = Depends(get_db),
):
    """Generate embeddings for the given input."""
    profile, client, _ = await get_profile_and_client(request.model_profile_id, session)

    try:
        async with client:
            response = await client.post(
                "/embeddings",
                json={
                    "input": request.input,
                    "model": request.model,
                },
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rerank", response_model=RerankResponse)
async def rerank_documents(
    request: RerankRequest,
    session: AsyncSession = Depends(get_db),
):
    """Rerank documents based on query relevance."""
    profile, client, _ = await get_profile_and_client(request.model_profile_id, session)

    try:
        async with client:
            # Try standard rerank endpoint first
            response = await client.post(
                "/rerank",
                json={
                    "query": request.query,
                    "documents": request.documents,
                    "model": request.model,
                    "top_n": request.top_n,
                },
            )
            response.raise_for_status()
            data = response.json()

            # Normalize response format
            results = []
            for item in data.get("results", data.get("data", [])):
                results.append(RerankResult(
                    index=item.get("index", 0),
                    document=request.documents[item.get("index", 0)],
                    relevance_score=item.get("relevance_score", item.get("score", 0)),
                ))

            return RerankResponse(
                model=request.model,
                results=results,
                usage=data.get("usage"),
            )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/images/generations", response_model=ImageGenerationResponse)
async def generate_image(
    request: ImageGenerationRequest,
    session: AsyncSession = Depends(get_db),
):
    """Generate images based on text prompt."""
    profile, client, _ = await get_profile_and_client(request.model_profile_id, session)

    try:
        async with client:
            response = await client.post(
                "/images/generations",
                json={
                    "prompt": request.prompt,
                    "model": request.model,
                    "n": request.n,
                    "size": request.size,
                    "quality": request.quality,
                    "style": request.style,
                },
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio/transcriptions", response_model=AudioTranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str = Form(...),
    model_profile_id: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    response_format: Optional[str] = Form("json"),
    session: AsyncSession = Depends(get_db),
):
    """Transcribe audio to text."""
    profile, client, api_key = await get_profile_and_client(model_profile_id, session)

    try:
        file_content = await file.read()

        async with client:
            # Need to use multipart form data for file upload
            files = {
                "file": (file.filename, file_content, file.content_type or "audio/mpeg"),
            }
            data = {
                "model": model,
            }
            if language:
                data["language"] = language
            if response_format:
                data["response_format"] = response_format

            response = await client.post(
                "/audio/transcriptions",
                files=files,
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
            )
            response.raise_for_status()

            result = response.json()
            return AudioTranscriptionResponse(
                text=result.get("text", ""),
                language=result.get("language"),
                duration=result.get("duration"),
                words=result.get("words"),
            )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio/speech")
async def text_to_speech(
    request: TextToSpeechRequest,
    session: AsyncSession = Depends(get_db),
):
    """Convert text to speech."""
    profile, client, _ = await get_profile_and_client(request.model_profile_id, session)

    try:
        async with client:
            response = await client.post(
                "/audio/speech",
                json={
                    "input": request.input,
                    "model": request.model,
                    "voice": request.voice,
                    "speed": request.speed,
                    "response_format": request.response_format,
                },
            )
            response.raise_for_status()

            # Return audio as streaming response
            content_type = "audio/mpeg"
            if request.response_format == "opus":
                content_type = "audio/opus"
            elif request.response_format == "aac":
                content_type = "audio/aac"
            elif request.response_format == "flac":
                content_type = "audio/flac"
            elif request.response_format == "wav":
                content_type = "audio/wav"

            return StreamingResponse(
                io.BytesIO(response.content),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"attachment; filename=speech.{request.response_format or 'mp3'}",
                },
            )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def get_models_by_capability(
    capability: str,
    session: AsyncSession = Depends(get_db),
):
    """Get available models for a specific capability."""
    from sqlalchemy import select

    query = select(ChatModelProfile).where(
        ChatModelProfile.enabled == True,
        ChatModelProfile.capabilities.contains([capability]),
    )

    result = await session.execute(query)
    profiles = result.scalars().all()

    return [
        {
            "profile_id": p.id,
            "profile_name": p.name,
            "models": p.available_models,
        }
        for p in profiles
    ]
