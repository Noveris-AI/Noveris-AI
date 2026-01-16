"""
Model market database models.
Stores Hugging Face model metadata with search indexes and tags.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, JSON, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class HFModel(Base):
    """
    Hugging Face Model metadata table.
    Stores synchronized model information from Hugging Face Hub.
    """
    __tablename__ = "hf_models"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(255), unique=True, nullable=False, index=True)  # e.g. "meta-llama/Llama-2-7b"
    sha = Column(String(255), nullable=True)  # Model commit SHA for change detection
    last_modified = Column(DateTime, nullable=True, index=True)  # For incremental sync

    # Basic model info
    author = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, nullable=True)
    downloads = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    tags = Column(JSON, nullable=True)  # List of tags from HF
    pipeline_tag = Column(String(100), nullable=True, index=True)  # e.g. "text-generation", "rerank"
    library_name = Column(String(100), nullable=True)

    # Model metadata
    model_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    card_data = Column(JSON, nullable=True)  # Full model card data
    config = Column(JSON, nullable=True)  # Model config
    transformers_info = Column(JSON, nullable=True)  # Specific info from transformers

    # Indexing fields for search
    indexed_tags = Column(JSON, nullable=True)  # Normalized tags for filtering
    indexed_categories = Column(JSON, nullable=True)  # Categories for classification

    # Sync tracking
    synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    details_fetched = Column(Boolean, default=False)  # Whether full details were fetched
    detail_synced_at = Column(DateTime, nullable=True)

    # Source info
    source = Column(String(50), default="huggingface")  # huggingface or hf-mirror
    source_url = Column(String(500), nullable=True)  # Direct URL to model page

    # Indexes for search performance
    __table_args__ = (
        Index('ix_hf_models_model_id', 'model_id'),
        Index('ix_hf_models_author', 'author'),
        Index('ix_hf_models_pipeline_tag', 'pipeline_tag'),
        Index('ix_hf_models_last_modified', 'last_modified'),
        Index('ix_hf_models_likes', 'likes'),
        Index('ix_hf_models_downloads', 'downloads'),
    )


class ModelSyncLog(Base):
    """
    Model synchronization log table.
    Tracks sync operations and their status.
    """
    __tablename__ = "model_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    sync_type = Column(String(20), nullable=False)  # 'full' or 'incremental'
    status = Column(String(20), nullable=False)  # 'pending', 'running', 'completed', 'failed', 'cancelled'

    # Sync metrics
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    total_models = Column(Integer, default=0)
    synced_models = Column(Integer, default=0)
    updated_models = Column(Integer, default=0)
    failed_models = Column(Integer, default=0)
    skipped_models = Column(Integer, default=0)

    # Sync configuration
    source = Column(String(50), default="huggingface")  # huggingface or hf-mirror
    watermark_last_modified = Column(DateTime, nullable=True)  # For incremental sync

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)

    # Progress tracking
    current_page = Column(Integer, default=0)
    total_pages = Column(Integer, default=0)
    progress_percentage = Column(Integer, default=0)

    # Additional info
    triggered_by = Column(String(100), default="system")  # 'system', 'user', 'cron'
    cancellation_requested = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AIRecommendationConfig(Base):
    """
    AI Recommendation configuration.
    Stores the LLM endpoint configuration for model recommendations.
    """
    __tablename__ = "ai_recommendation_config"

    id = Column(Integer, primary_key=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # LLM Configuration
    provider = Column(String(50), nullable=False)  # 'openai', 'anthropic', 'local', 'custom'
    model_name = Column(String(255), nullable=False)  # e.g. "gpt-4", "claude-3-opus"
    endpoint_url = Column(String(500), nullable=False)  # API endpoint
    api_key = Column(String(500), nullable=True)  # API key (optional for local models)
    api_key_required = Column(Boolean, default=True)

    # Additional config
    temperature = Column(Integer, default=70)  # 0-100 scale
    max_tokens = Column(Integer, default=2000)
    system_prompt = Column(Text, nullable=True)  # Custom system prompt (optional)
    additional_config = Column(JSON, nullable=True)  # Any additional provider-specific config

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Only one active config at a time
    __table_args__ = (
        Index('ix_ai_rec_config_active', 'is_active'),
    )


class UserModelBookmark(Base):
    """
    User bookmarked/favorited models.
    """
    __tablename__ = "user_model_bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(String(255), nullable=False)  # HF model ID, no FK constraint as model_id is not PK
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Unique constraint: one bookmark per user per model
    __table_args__ = (
        Index('ix_user_bookmarks_user_id', 'user_id'),
        Index('ix_user_bookmarks_model_id', 'model_id'),
    )
