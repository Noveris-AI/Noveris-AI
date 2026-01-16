"""
Model Market Business Service.

This service handles business logic for the model market API.
It only reads from the local database, independent from the sync service.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc, asc, text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_market import HFModel, ModelSyncLog, AIRecommendationConfig
from app.schemas.model_market import (
    ModelCardBrief,
    ModelCardDetail,
    ModelListResponse,
    ModelSearchRequest,
    ModelMarketStats,
    PipelineTagStats,
    CategoryStats,
)


class ModelMarketService:
    """Service for model market business operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stats(self) -> ModelMarketStats:
        """Get overall model market statistics."""
        # Total models
        total_models_result = await self.db.execute(
            select(func.count(HFModel.id))
        )
        total_models = total_models_result.scalar() or 0

        # Total authors (unique)
        total_authors_result = await self.db.execute(
            select(func.count(func.distinct(HFModel.author)))
        )
        total_authors = total_authors_result.scalar() or 0

        # Pipeline tag statistics
        pipeline_stats_result = await self.db.execute(
            select(HFModel.pipeline_tag, func.count(HFModel.id).label('count'))
            .filter(HFModel.pipeline_tag.isnot(None))
            .group_by(HFModel.pipeline_tag)
        )
        pipeline_stats = pipeline_stats_result.all()

        pipeline_tags = [
            PipelineTagStats(tag=tag, display_name=tag.replace("-", " ").title(), count=count)
            for tag, count in pipeline_stats
        ]

        # Category statistics (from indexed_categories)
        # Get all unique categories and their counts
        category_counts: Dict[str, int] = {}
        models_result = await self.db.execute(
            select(HFModel.indexed_categories)
            .filter(HFModel.indexed_categories.isnot(None))
        )
        models = models_result.scalars().all()

        for model_cats in models:
            if model_cats:
                for cat in model_cats:
                    category_counts[cat] = category_counts.get(cat, 0) + 1

        categories = [
            CategoryStats(category=cat, count=count)
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Last sync info
        last_sync_result = await self.db.execute(
            select(ModelSyncLog)
            .order_by(ModelSyncLog.created_at.desc())
            .limit(1)
        )
        last_sync = last_sync_result.scalar_one_or_none()

        last_sync_time = last_sync.created_at if last_sync else None
        sync_status = last_sync.status if last_sync else None

        return ModelMarketStats(
            total_models=total_models,
            total_authors=total_authors,
            pipeline_tags=pipeline_tags,
            categories=categories,
            last_sync=last_sync_time,
            sync_status=sync_status,
        )

    async def search_models(self, params: ModelSearchRequest) -> ModelListResponse:
        """
        Search models with filters and pagination.

        Args:
            params: Search parameters including query, filters, sort, and pagination

        Returns:
            ModelListResponse with matching models
        """
        # Build base query
        query = select(HFModel)

        # Apply search filters
        conditions = []
        if params.query:
            search_term = f"%{params.query}%"
            conditions.append(
                or_(
                    HFModel.model_id.ilike(search_term),
                    HFModel.model_name.ilike(search_term),
                    HFModel.description.ilike(search_term),
                    HFModel.author.ilike(search_term),
                )
            )

        if params.pipeline_tag:
            conditions.append(HFModel.pipeline_tag == params.pipeline_tag)

        if params.author:
            conditions.append(HFModel.author == params.author)

        if params.tags:
            for tag in params.tags:
                # Cast to jsonb and use @> operator for array contains
                conditions.append(
                    text(f"indexed_tags::jsonb @> '[\"{tag}\"]'::jsonb")
                )

        if params.categories:
            for cat in params.categories:
                # Cast to jsonb and use @> operator for array contains
                conditions.append(
                    text(f"indexed_categories::jsonb @> '[\"{cat}\"]'::jsonb")
                )

        if conditions:
            query = query.filter(and_(*conditions))

        # Get total count before pagination
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Apply sorting
        sort_column = HFModel.last_modified  # default
        if params.sort_by == "downloads":
            sort_column = HFModel.downloads
        elif params.sort_by == "likes":
            sort_column = HFModel.likes
        elif params.sort_by == "model_name":
            sort_column = HFModel.model_name
        elif params.sort_by == "author":
            sort_column = HFModel.author

        if params.sort_order == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        # Apply pagination
        offset = (params.page - 1) * params.page_size
        query = query.offset(offset).limit(params.page_size)

        # Execute query
        models_result = await self.db.execute(query)
        models = models_result.scalars().all()

        # Calculate total pages (max 100)
        total_pages = min(100, (total + params.page_size - 1) // params.page_size) if total > 0 else 1

        return ModelListResponse(
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages,
            models=[ModelCardBrief.model_validate(m) for m in models],
        )

    async def get_model_detail(self, model_id: str) -> Optional[ModelCardDetail]:
        """Get detailed information about a specific model."""
        result = await self.db.execute(
            select(HFModel).filter(HFModel.model_id == model_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return ModelCardDetail.model_validate(model)

    async def get_sync_status(self, limit: int = 10) -> List[dict]:
        """
        Get recent sync status entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of sync status dictionaries
        """
        result = await self.db.execute(
            select(ModelSyncLog)
            .order_by(ModelSyncLog.created_at.desc())
            .limit(limit)
        )
        sync_logs = result.scalars().all()

        return [
            {
                "id": log.id,
                "sync_type": log.sync_type,
                "status": log.status,
                "started_at": log.started_at,
                "completed_at": log.completed_at,
                "total_models": log.total_models,
                "synced_models": log.synced_models or 0,
                "updated_models": log.updated_models or 0,
                "failed_models": log.failed_models or 0,
                "skipped_models": log.skipped_models or 0,
                "current_page": log.current_page or 0,
                "total_pages": log.total_pages or 0,
                "progress_percentage": log.progress_percentage or 0,
                "error_message": log.error_message,
                "source": log.source,
                "triggered_by": log.triggered_by,
            }
            for log in sync_logs
        ]

    async def get_latest_sync_status(self) -> Optional[dict]:
        """Get the most recent sync status."""
        result = await self.db.execute(
            select(ModelSyncLog)
            .order_by(ModelSyncLog.created_at.desc())
            .limit(1)
        )
        sync_log = result.scalar_one_or_none()

        if not sync_log:
            return None

        return {
            "id": sync_log.id,
            "sync_type": sync_log.sync_type,
            "status": sync_log.status,
            "started_at": sync_log.started_at,
            "completed_at": sync_log.completed_at,
            "total_models": sync_log.total_models,
            "synced_models": sync_log.synced_models or 0,
            "updated_models": sync_log.updated_models or 0,
            "failed_models": sync_log.failed_models or 0,
            "skipped_models": sync_log.skipped_models or 0,
            "current_page": sync_log.current_page or 0,
            "total_pages": sync_log.total_pages or 0,
            "progress_percentage": sync_log.progress_percentage or 0,
            "error_message": sync_log.error_message,
            "source": sync_log.source,
            "triggered_by": sync_log.triggered_by,
        }

    async def create_sync_log(
        self,
        sync_type: str,
        source: str = "huggingface",
        triggered_by: str = "user",
    ) -> ModelSyncLog:
        """Create a new sync log entry."""
        sync_log = ModelSyncLog(
            sync_type=sync_type,
            status="pending",
            source=source,
            triggered_by=triggered_by,
        )
        self.db.add(sync_log)
        await self.db.commit()
        await self.db.refresh(sync_log)
        return sync_log

    async def get_ai_config(self) -> Optional[AIRecommendationConfig]:
        """Get the active AI recommendation configuration."""
        result = await self.db.execute(
            select(AIRecommendationConfig)
            .filter(AIRecommendationConfig.is_active == True)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_ai_config(
        self,
        provider: str,
        model_name: str,
        endpoint_url: str,
        api_key: Optional[str] = None,
        temperature: int = 70,
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None,
    ) -> AIRecommendationConfig:
        """
        Create or update AI recommendation configuration.

        If an active config exists, it will be deactivated first.
        """
        # Deactivate existing configs
        await self.db.execute(
            select(AIRecommendationConfig)
            .filter(AIRecommendationConfig.is_active == True)
        )

        # Get all active configs and deactivate them
        result = await self.db.execute(
            select(AIRecommendationConfig)
            .filter(AIRecommendationConfig.is_active == True)
        )
        active_configs = result.scalars().all()
        for config in active_configs:
            config.is_active = False

        # Create new config
        config = AIRecommendationConfig(
            provider=provider,
            model_name=model_name,
            endpoint_url=endpoint_url,
            api_key=api_key,
            api_key_required=api_key is not None,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            is_active=True,
        )
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def ai_recommend(
        self,
        query: str,
        max_results: int = 5,
    ) -> Tuple[List[dict], str]:
        """
        Get AI-powered model recommendations.

        This uses the configured LLM to recommend models based on the query.
        """
        import httpx

        # Get AI config
        config = await self.get_ai_config()
        if not config:
            raise ValueError("AI recommendation not configured. Please configure it first.")

        # Build system prompt for recommendations
        default_system_prompt = """You are an AI assistant that helps users find the best Hugging Face models for their needs.

When a user asks for a model recommendation:
1. Analyze their requirements carefully
2. Consider multiple factors: model performance, popularity (downloads/likes), recent updates, community adoption
3. Recommend 5 specific models that best match their needs
4. For each recommendation, explain WHY you chose it

Your response must be in JSON format:
{
  "recommendations": [
    {
      "model_id": "org/model-name",
      "reason": "Clear explanation of why this model is recommended (2-3 sentences)"
    }
  ]
}

Only recommend models that exist on Hugging Face. Use well-known, reputable models when possible."""

        system_prompt = config.system_prompt or default_system_prompt

        # Build API request based on provider
        headers = {"Content-Type": "application/json"}

        if config.provider == "openai":
            payload = {
                "model": config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                "temperature": config.temperature / 100,
                "max_tokens": config.max_tokens,
            }
            if config.api_key:
                headers["Authorization"] = f"Bearer {config.api_key}"

        elif config.provider == "anthropic":
            payload = {
                "model": config.model_name,
                "messages": [
                    {"role": "user", "content": f"{system_prompt}\n\nUser query: {query}"}
                ],
                "temperature": config.temperature / 100,
                "max_tokens": config.max_tokens,
            }
            if config.api_key:
                headers["x-api-key"] = config.api_key
                headers["anthropic-version"] = "2023-06-01"

        else:  # Custom / Local (OpenAI-compatible)
            payload = {
                "model": config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                "temperature": config.temperature / 100,
                "max_tokens": config.max_tokens,
            }
            if config.api_key:
                headers["Authorization"] = f"Bearer {config.api_key}"

        # Make request
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                config.endpoint_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        # Parse response based on provider
        if config.provider == "anthropic":
            content = result.get("content", [{}])[0].get("text", "")
        else:
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Parse JSON response
        import json
        try:
            # Try to extract JSON from content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            parsed = json.loads(json_str)
            recommendations_data = parsed.get("recommendations", [])
        except json.JSONDecodeError:
            # Fallback: try to parse model IDs from text
            recommendations_data = []
            lines = content.split("\n")
            for line in lines:
                if "/" in line and not line.strip().startswith("#"):
                    # Extract model_id from line
                    parts = line.split("/")
                    if len(parts) >= 2:
                        model_id = "/".join(parts[0:2]).strip("`*").strip()
                        if model_id.count("/") == 1:
                            recommendations_data.append({
                                "model_id": model_id,
                                "reason": "Recommended based on your query."
                            })

        # Get full model info for recommendations
        recommendations = []
        for rec in recommendations_data[:max_results]:
            model_id = rec.get("model_id", "")
            result = await self.db.execute(
                select(HFModel).filter(HFModel.model_id == model_id)
            )
            model = result.scalar_one_or_none()

            if model:
                recommendations.append({
                    "model_id": model.model_id,
                    "model_name": model.model_name,
                    "author": model.author,
                    "description": model.description,
                    "pipeline_tag": model.pipeline_tag,
                    "downloads": model.downloads,
                    "likes": model.likes,
                    "reason": rec.get("reason", "Recommended based on your query."),
                })
            else:
                # Model not in DB yet, still include it
                recommendations.append({
                    "model_id": model_id,
                    "model_name": model_id.split("/")[-1] if "/" in model_id else model_id,
                    "author": model_id.split("/")[0] if "/" in model_id else None,
                    "description": None,
                    "pipeline_tag": None,
                    "downloads": 0,
                    "likes": 0,
                    "reason": rec.get("reason", "Recommended based on your query."),
                })

        return recommendations, query

    async def get_trending_models(self, limit: int = 10) -> List[ModelCardBrief]:
        """Get trending models based on recent likes and downloads."""
        # Get models with most activity in the last 7 days
        since = datetime.utcnow() - timedelta(days=7)

        result = await self.db.execute(
            select(HFModel)
            .filter(HFModel.last_modified >= since)
            .order_by(desc(HFModel.likes), desc(HFModel.downloads))
            .limit(limit)
        )
        models = result.scalars().all()

        return [ModelCardBrief.model_validate(m) for m in models]

    async def get_recent_models(self, limit: int = 10) -> List[ModelCardBrief]:
        """Get recently added/updated models."""
        result = await self.db.execute(
            select(HFModel)
            .order_by(desc(HFModel.last_modified))
            .limit(limit)
        )
        models = result.scalars().all()

        return [ModelCardBrief.model_validate(m) for m in models]


def get_model_market_service(db: AsyncSession) -> ModelMarketService:
    """Get model market service instance."""
    return ModelMarketService(db)
