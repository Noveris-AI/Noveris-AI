"""
Model Market API Routes.

This module provides API endpoints for the Hugging Face model market.
All endpoints read from the local database only, independent from the sync service.
Sync operations are dispatched to Celery workers for independent processing.

IMPORTANT: Routes with path parameters (like /{model_id}) must be defined LAST
to avoid catching specific routes like /categories, /sync/status, etc.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user_optional
from app.models.user import User
from app.models.model_market import HFModel, ModelSyncLog
from app.schemas.model_market import (
    ModelCardDetail,
    ModelListResponse,
    ModelSearchRequest,
    SyncStatusResponse,
    SyncTriggerRequest,
    SyncTriggerResponse,
    AIRecommendConfigRequest,
    AIRecommendConfigResponse,
    AIRecommendRequest,
    AIRecommendResponse,
    AIRecommendModel,
    ModelMarketStats,
    ModelCardBrief,
)
from app.services.model_market_service import ModelMarketService, get_model_market_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["model-market"])


# ============== Model Listing & Search ==============

@router.get("/stats", response_model=ModelMarketStats)
async def get_market_stats(
    db: AsyncSession = Depends(get_db),
) -> ModelMarketStats:
    """
    Get model market statistics.

    Returns total models, authors, pipeline tag counts, and categories.
    """
    service = get_model_market_service(db)
    return await service.get_stats()


@router.get("", response_model=ModelListResponse)
async def list_models(
    query: Optional[str] = Query(None, description="Search query"),
    categories: Optional[str] = Query(None, description="Filter by categories (comma-separated)"),
    sort_by: Optional[str] = Query("last_modified", description="Sort field"),
    sort_order: Optional[str] = Query("desc", description="Sort order"),
    page: int = Query(1, ge=1, le=100, description="Page number (max 100)"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> ModelListResponse:
    """
    List/search models with filters and pagination.

    - **query**: Search in model_id, model_name, description, author
    - **categories**: Comma-separated list of categories
    - **sort_by**: Field to sort by (last_modified, downloads, likes, model_name, author)
    - **sort_order**: asc or desc
    - **page**: Page number (max 100 pages)
    - **page_size**: Items per page (1-100)
    """
    # Parse comma-separated parameters
    category_list = categories.split(",") if categories else None

    params = ModelSearchRequest(
        query=query,
        categories=category_list,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    service = get_model_market_service(db)
    return await service.search_models(params)


@router.get("/trending", response_model=list[ModelCardBrief])
async def get_trending_models(
    limit: int = Query(10, ge=1, le=50, description="Number of models to return"),
    db: AsyncSession = Depends(get_db),
) -> list[ModelCardBrief]:
    """Get trending models based on recent activity."""
    service = get_model_market_service(db)
    return await service.get_trending_models(limit)


@router.get("/recent", response_model=list[ModelCardBrief])
async def get_recent_models(
    limit: int = Query(10, ge=1, le=50, description="Number of models to return"),
    db: AsyncSession = Depends(get_db),
) -> list[ModelCardBrief]:
    """Get recently updated models."""
    service = get_model_market_service(db)
    return await service.get_recent_models(limit)


# ============== Sync Management ==============

@router.get("/sync/status", response_model=list[SyncStatusResponse])
async def get_sync_status(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[SyncStatusResponse]:
    """Get recent sync status logs."""
    service = get_model_market_service(db)
    return await service.get_sync_status(limit)


@router.get("/sync/latest", response_model=Optional[SyncStatusResponse])
async def get_latest_sync_status(
    db: AsyncSession = Depends(get_db),
) -> Optional[SyncStatusResponse]:
    """Get the most recent sync status."""
    service = get_model_market_service(db)
    status = await service.get_latest_sync_status()

    if not status:
        return None

    return SyncStatusResponse(**status)


@router.post("/sync/trigger", response_model=SyncTriggerResponse)
async def trigger_sync(
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> SyncTriggerResponse:
    """
    Trigger a model sync operation.

    - **sync_type**: "full" or "incremental"
    - **source**: "huggingface" or "hf-mirror"

    Full sync: Synchronizes all models from Hugging Face (may take hours).
    Incremental sync: Only syncs models updated since last sync (much faster).

    Rate limiting applies to prevent excessive sync triggers.
    """
    service = get_model_market_service(db)

    # Check if there's already a running sync
    latest_status = await service.get_latest_sync_status()
    if latest_status and latest_status.get("status") in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"A sync is already {latest_status.get('status')}. Please wait for it to complete."
        )

    # Check for rate limiting (prevent excessive sync triggers)
    recent_syncs = await service.get_sync_status(limit=5)
    recent_completed = [s for s in recent_syncs if s.get("status") == "completed"]

    # Check if there was a sync in the last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    for sync in recent_completed:
        if sync.get("completed_at") and sync["completed_at"] > one_hour_ago:
            raise HTTPException(
                status_code=429,
                detail="Please wait at least 1 hour between sync operations."
            )

    # Create sync log
    triggered_by = current_user.email if current_user else "user"
    sync_log = await service.create_sync_log(
        sync_type=request.sync_type,
        source=request.source,
        triggered_by=triggered_by,
    )

    # Import Celery tasks (lazy import to avoid circular dependency)
    try:
        from app.worker.sync_tasks import full_sync_task, incremental_sync_task

        # Dispatch to Celery for background processing
        # expires=600 means the task will be cancelled if not picked up within 10 minutes
        if request.sync_type == "full":
            # Use Celery for independent processing
            full_sync_task.apply_async(
                args=[sync_log.id, request.source],
                expires=600,  # Task expires if not picked up within 10 minutes
            )
        else:
            incremental_sync_task.apply_async(
                args=[sync_log.id, request.source],
                expires=60,  # Task expires if not picked up within 60 seconds
            )

    except Exception:  # Catch any Celery errors and fall back to BackgroundTasks
        # Fallback to BackgroundTasks if Celery is not configured
        from app.services.model_sync_service import run_full_sync_task, run_incremental_sync_task

        if request.sync_type == "full":
            background_tasks.add_task(run_full_sync_task, sync_log.id, request.source)
        else:
            background_tasks.add_task(run_incremental_sync_task, sync_log.id, request.source)

    return SyncTriggerResponse(
        sync_log_id=sync_log.id,
        message=f"{request.sync_type.capitalize()} sync started. Check /models/sync/status for progress.",
        sync_type=request.sync_type,
        status="pending",
    )


@router.post("/sync/{sync_log_id}/cancel")
async def cancel_sync(
    sync_log_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel an ongoing sync operation.

    - **sync_log_id**: The ID of the sync log to cancel
    """
    # Try to use Celery task for cancellation
    try:
        from app.worker.sync_tasks import cancel_sync_task

        # Dispatch to Celery
        cancel_sync_task.delay(sync_log_id)

    except ImportError:
        # Fallback to direct service call
        from app.services.model_sync_service import get_sync_service

        # Verify the sync log exists and is running
        result = await db.execute(
            select(ModelSyncLog).filter(ModelSyncLog.id == sync_log_id)
        )
        sync_log = result.scalar_one_or_none()

        if not sync_log:
            raise HTTPException(status_code=404, detail="Sync log not found")

        if sync_log.status not in ("pending", "running"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel sync with status '{sync_log.status}'"
            )

        service = get_sync_service()
        service.cancel_sync(sync_log_id)

    return {"message": "Sync cancellation requested"}


# ============== AI Recommendation ==============

@router.get("/ai-config", response_model=Optional[AIRecommendConfigResponse])
async def get_ai_config(
    db: AsyncSession = Depends(get_db),
) -> Optional[AIRecommendConfigResponse]:
    """Get the current AI recommendation configuration."""
    service = get_model_market_service(db)
    config = await service.get_ai_config()

    if not config:
        return None

    return AIRecommendConfigResponse.model_validate(config)


@router.post("/ai-config", response_model=AIRecommendConfigResponse)
async def update_ai_config(
    request: AIRecommendConfigRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> AIRecommendConfigResponse:
    """
    Configure AI recommendation settings.

    Configure the LLM endpoint used for model recommendations.
    Supports OpenAI, Anthropic, and custom OpenAI-compatible endpoints.

    For local models without API keys, set api_key to null or omit it.
    """
    service = get_model_market_service(db)

    config = await service.update_ai_config(
        provider=request.provider,
        model_name=request.model_name,
        endpoint_url=request.endpoint_url,
        api_key=request.api_key,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        system_prompt=request.system_prompt,
    )

    return AIRecommendConfigResponse.model_validate(config)


@router.post("/ai-recommend", response_model=AIRecommendResponse)
async def ai_recommend(
    request: AIRecommendRequest,
    db: AsyncSession = Depends(get_db),
) -> AIRecommendResponse:
    """
    Get AI-powered model recommendations.

    Uses the configured LLM to recommend models based on natural language queries.

    Example query: "推荐一个rerank模型" or "Recommend a good text generation model"

    - **query**: Natural language query describing what you're looking for
    - **max_results**: Maximum number of recommendations to return (1-10)
    """
    service = get_model_market_service(db)

    try:
        recommendations, query = await service.ai_recommend(
            query=request.query,
            max_results=request.max_results,
        )

        return AIRecommendResponse(
            recommendations=[AIRecommendModel(**r) for r in recommendations],
            query=query,
            total_found=len(recommendations),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"AI recommendation failed: {e}")
        raise HTTPException(status_code=500, detail="AI recommendation service unavailable")


# ============== Pipeline Tags & Categories ==============

@router.get("/pipeline-tags", response_model=list[dict])
async def get_pipeline_tags(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all available pipeline tags with their display names."""
    # Common pipeline tags with display names
    pipeline_tags = [
        {"tag": "text-generation", "name": "Text Generation"},
        {"tag": "text2text-generation", "name": "Text-to-Text Generation"},
        {"tag": "fill-mask", "name": "Fill Mask"},
        {"tag": "token-classification", "name": "Token Classification"},
        {"tag": "text-classification", "name": "Text Classification"},
        {"tag": "question-answering", "name": "Question Answering"},
        {"tag": "summarization", "name": "Summarization"},
        {"tag": "translation", "name": "Translation"},
        {"tag": "sentence-similarity", "name": "Sentence Similarity"},
        {"tag": "feature-extraction", "name": "Feature Extraction"},
        {"tag": "rerank", "name": "Rerank"},
        {"tag": "text-to-speech", "name": "Text-to-Speech"},
        {"tag": "automatic-speech-recognition", "name": "Speech Recognition"},
        {"tag": "image-classification", "name": "Image Classification"},
        {"tag": "object-detection", "name": "Object Detection"},
        {"tag": "image-segmentation", "name": "Image Segmentation"},
        {"tag": "text-to-image", "name": "Text-to-Image"},
        {"tag": "image-to-image", "name": "Image-to-Image"},
        {"tag": "zero-shot-classification", "name": "Zero-Shot Classification"},
        {"tag": "zero-shot-image-classification", "name": "Zero-Shot Image Classification"},
        {"tag": "reinforcement-learning", "name": "Reinforcement Learning"},
        {"tag": "robotics", "name": "Robotics"},
        {"tag": "tabular-classification", "name": "Tabular Classification"},
        {"tag": "tabular-regression", "name": "Tabular Regression"},
        {"tag": "audio-classification", "name": "Audio Classification"},
        {"tag": "audio-to-audio", "name": "Audio-to-Audio"},
    ]

    # Add counts from database
    for tag_info in pipeline_tags:
        result = await db.execute(
            select(func.count(HFModel.id)).filter(
                HFModel.pipeline_tag == tag_info["tag"]
            )
        )
        count = result.scalar() or 0
        tag_info["count"] = count

    return [t for t in pipeline_tags if t["count"] > 0]


@router.get("/categories", response_model=list[dict])
async def get_categories(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all available model categories."""
    service = get_model_market_service(db)
    stats = await service.get_stats()
    return [
        {"category": cat.category, "count": cat.count}
        for cat in stats.categories
    ]


# ============== Model Detail (MUST BE LAST - has path parameter) ==============

@router.get("/{model_id:path}", response_model=ModelCardDetail)
async def get_model_detail(
    model_id: str,
    db: AsyncSession = Depends(get_db),
) -> ModelCardDetail:
    """
    Get detailed information about a specific model.

    - **model_id**: Hugging Face model ID (e.g., "meta-llama/Llama-2-7b")

    NOTE: This route MUST be defined last to avoid catching specific routes like
    /categories, /sync/status, etc.
    """
    service = get_model_market_service(db)
    model = await service.get_model_detail(model_id)

    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    return model
