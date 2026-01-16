"""
Pydantic schemas for Model Market API.
"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict


# ============== Model Schemas ==============

class ModelCardBrief(BaseModel):
    """Brief model info for list view."""
    model_id: str
    author: Optional[str] = None
    model_name: Optional[str] = None
    description: Optional[str] = None
    pipeline_tag: Optional[str] = None
    tags: List[str] = []
    downloads: int = 0
    likes: int = 0
    last_modified: Optional[datetime] = None
    source_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ModelCardDetail(ModelCardBrief):
    """Full model info for detail view."""
    sha: Optional[str] = None
    created_at: Optional[datetime] = None
    library_name: Optional[str] = None
    card_data: Optional[dict] = None
    config: Optional[dict] = None
    transformers_info: Optional[dict] = None
    indexed_tags: Optional[List[str]] = []
    indexed_categories: Optional[List[str]] = []
    synced_at: Optional[datetime] = None
    details_fetched: bool = False

    model_config = ConfigDict(from_attributes=True)


class ModelListResponse(BaseModel):
    """Response for model list endpoint."""
    total: int
    page: int
    page_size: int
    total_pages: int
    models: List[ModelCardBrief]


class ModelSearchRequest(BaseModel):
    """Request for model search."""
    query: Optional[str] = None
    pipeline_tag: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    sort_by: Optional[str] = "last_modified"  # last_modified, downloads, likes
    sort_order: Optional[str] = "desc"  # desc, asc
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ============== Sync Schemas ==============

class SyncStatusResponse(BaseModel):
    """Response for sync status endpoint."""
    id: int
    sync_type: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_models: int = 0
    synced_models: int = 0
    updated_models: int = 0
    failed_models: int = 0
    skipped_models: int = 0
    current_page: int = 0
    total_pages: int = 0
    progress_percentage: int = 0
    error_message: Optional[str] = None
    source: str = "huggingface"
    triggered_by: str = "system"

    model_config = ConfigDict(from_attributes=True)


class SyncTriggerRequest(BaseModel):
    """Request to trigger a sync."""
    sync_type: str = Field(..., pattern="^(full|incremental)$")
    source: str = Field(default="huggingface", pattern="^(huggingface|hf-mirror)$")


class SyncTriggerResponse(BaseModel):
    """Response after triggering a sync."""
    sync_log_id: int
    message: str
    sync_type: str
    status: str


# ============== AI Recommendation Schemas ==============

class AIRecommendConfigRequest(BaseModel):
    """Request to configure AI recommendation."""
    provider: str = Field(..., description="LLM provider: openai, anthropic, local, custom")
    model_name: str = Field(..., description="Model name, e.g. gpt-4, claude-3-opus")
    endpoint_url: str = Field(..., description="API endpoint URL")
    api_key: Optional[str] = Field(None, description="API key (optional for local models)")
    temperature: Optional[int] = Field(default=70, ge=0, le=100)
    max_tokens: Optional[int] = Field(default=2000, ge=100, le=8000)
    system_prompt: Optional[str] = Field(None, description="Custom system prompt (optional)")


class AIRecommendConfigResponse(BaseModel):
    """Response for AI recommendation config."""
    id: int
    provider: str
    model_name: str
    endpoint_url: str
    api_key_required: bool = True
    temperature: int = 70
    max_tokens: int = 2000
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AIRecommendRequest(BaseModel):
    """Request for AI model recommendation."""
    query: str = Field(..., description="User's query, e.g. '推荐一个rerank模型'")
    max_results: Optional[int] = Field(default=5, ge=1, le=10)


class AIRecommendModel(BaseModel):
    """Single recommended model."""
    model_id: str
    model_name: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    pipeline_tag: Optional[str] = None
    downloads: int = 0
    likes: int = 0
    reason: str  # Why this model is recommended


class AIRecommendResponse(BaseModel):
    """Response for AI recommendation."""
    recommendations: List[AIRecommendModel]
    query: str
    total_found: int


# ============== Category/Filter Schemas ==============

class PipelineTagStats(BaseModel):
    """Statistics for pipeline tags."""
    tag: str
    display_name: str
    count: int
    description: Optional[str] = None


class CategoryStats(BaseModel):
    """Statistics for categories."""
    category: str
    count: int


class ModelMarketStats(BaseModel):
    """Overall model market statistics."""
    total_models: int
    total_authors: int
    pipeline_tags: List[PipelineTagStats]
    categories: List[CategoryStats]
    last_sync: Optional[datetime] = None
    sync_status: Optional[str] = None


# ============== Bookmark Schemas ==============

class BookmarkRequest(BaseModel):
    """Request to add/update bookmark."""
    model_id: str
    notes: Optional[str] = None


class BookmarkResponse(BaseModel):
    """Response for bookmark."""
    id: int
    user_id: int
    model_id: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BookmarkListResponse(BaseModel):
    """Response for bookmark list."""
    total: int
    bookmarks: List[ModelCardBrief]
