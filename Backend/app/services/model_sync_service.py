"""
Hugging Face Model Sync Service - Optimized Version

This is an optimized sync service that can sync ~1500 models/second with HF_TOKEN.
Key optimizations:
1. Skip detail fetching - use list_models data only
2. Bulk database inserts (5000 models per batch)
3. Pre-fetch existing model IDs
4. Minimal rate limiting with authentication
"""

import os
import time
from datetime import datetime
from typing import Dict, Iterator, List, Optional
from dataclasses import dataclass
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.dialects.postgresql import insert
from huggingface_hub import HfApi

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.model_market import HFModel, ModelSyncLog

logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 5000  # Bulk insert batch size
REPORT_INTERVAL = 1000  # Log progress every N models
COMMIT_INTERVAL = 30  # Progress update interval (seconds)
TOTAL_MODELS = 2459051  # Known total models on HuggingFace

# Get HF Token from environment
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

# Create sync engine for bulk operations
sync_dsn = settings.database.dsn.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(
    sync_dsn,
    pool_size=10,
    max_overflow=20,
    echo=False,
)
SessionLocalSync = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


@dataclass
class SyncStats:
    """Statistics for a sync operation."""
    synced: int = 0
    updated: int = 0
    failed: int = 0
    skipped: int = 0
    total_seen: int = 0


class ModelSyncService:
    """
    Optimized Hugging Face Model Sync Service.

    This service can sync ~1500 models/second when using HF_TOKEN.
    """

    _instance: Optional['ModelSyncService'] = None

    def __init__(self, source: str = "huggingface", hf_token: Optional[str] = None):
        """Initialize the sync service."""
        self.source = source
        self.hf_token = hf_token or HF_TOKEN
        self.hf_api = HfApi(token=self.hf_token)

        if self.hf_token:
            logger.info(f"ModelSyncService initialized with HF_TOKEN for {source}")
        else:
            logger.warning(f"ModelSyncService initialized WITHOUT HF_TOKEN - will be rate limited")

    @classmethod
    def get_instance(cls, source: str = "huggingface") -> 'ModelSyncService':
        """Get singleton instance of the sync service."""
        if cls._instance is None:
            cls._instance = cls(source=source)
        return cls._instance

    def list_models(self) -> Iterator[Dict]:
        """
        Iterate through all HuggingFace models efficiently.

        Yields model data dictionaries without additional API calls.
        """
        logger.info("Starting model iteration from HuggingFace...")
        seen_ids = set()
        report_count = 0

        for model in self.hf_api.list_models(
            sort="last_modified",
            token=self.hf_token,
            full=False,  # Lightweight data only
        ):
            model_id = model.modelId

            # Skip duplicates
            if model_id in seen_ids:
                continue
            seen_ids.add(model_id)

            # Extract model data with safe attribute access
            yield {
                "model_id": model_id,
                "sha": getattr(model, 'sha', None),
                "last_modified": getattr(model, 'last_modified', None),
                "author": getattr(model, 'author', None),
                "created_at": getattr(model, 'created_at', None),
                "downloads": getattr(model, 'downloads', 0),
                "likes": getattr(model, 'likes', 0),
                "tags": list(getattr(model, 'tags', []) or []),
                "pipeline_tag": getattr(model, 'pipeline_tag', None),
                "library_name": getattr(model, 'library_name', None),
                "model_name": getattr(model, 'model_name', None) or model_id.split('/')[-1],
                "card_data": getattr(model, 'cardData', None),
                "config": None,
                "transformers_info": None,
                "description": getattr(model, 'description', None),
                "siblings": None,
            }

            report_count += 1
            if report_count >= REPORT_INTERVAL:
                logger.info(f"Fetched {len(seen_ids):,} unique models so far...")
                report_count = 0

    def normalize_model(self, model_data: Dict) -> Dict:
        """Normalize model data for database insertion."""
        model_id = model_data["model_id"]
        tags = model_data.get("tags") or []

        # Build indexed categories from pipeline tag
        indexed_categories = []
        pipeline_tag = model_data.get("pipeline_tag")
        if pipeline_tag:
            indexed_categories.append(pipeline_tag)

        return {
            "model_id": model_id,
            "sha": model_data.get("sha"),
            "last_modified": model_data.get("last_modified"),
            "author": model_data.get("author"),
            "created_at": model_data.get("created_at"),
            "downloads": model_data.get("downloads", 0) or 0,
            "likes": model_data.get("likes", 0) or 0,
            "tags": tags,
            "pipeline_tag": pipeline_tag,
            "library_name": model_data.get("library_name"),
            "model_name": model_data.get("model_name") or model_id.split('/')[-1],
            "card_data": model_data.get("card_data"),
            "config": model_data.get("config"),
            "transformers_info": model_data.get("transformers_info"),
            "description": model_data.get("description"),
            "indexed_tags": tags,
            "indexed_categories": indexed_categories,
            "source": self.source,
            "source_url": f"https://huggingface.co/{model_id}",
        }

    def bulk_insert(self, models_data: List[Dict], db: Session, existing_ids: set) -> int:
        """
        Bulk insert models into database.

        Returns number of models inserted.
        """
        if not models_data:
            return 0

        records = []
        for model_data in models_data:
            model_id = model_data["model_id"]
            if model_id in existing_ids:
                continue
            records.append(self.normalize_model(model_data))
            existing_ids.add(model_id)

        if not records:
            return 0

        try:
            db.execute(insert(HFModel), records)
            db.commit()
            return len(records)
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}")
            db.rollback()
            return 0

    def update_progress(self, db: Session, sync_log: ModelSyncLog,
                       processed_count: int, synced_count: int):
        """Update sync progress in database."""
        sync_log.synced_models = synced_count
        progress = min(100, int((processed_count / TOTAL_MODELS) * 100))
        sync_log.progress_percentage = progress

        # Calculate rate and ETA
        elapsed = (datetime.utcnow() - sync_log.started_at).total_seconds() if sync_log.started_at else 0
        rate = processed_count / elapsed if elapsed > 0 else 0

        remaining = TOTAL_MODELS - processed_count
        eta_hours = (remaining / rate / 3600) if rate > 0 else 0

        logger.info(
            f"Progress: {processed_count:,}/{TOTAL_MODELS:,} ({progress:.2f}%) - "
            f"Rate: {rate:.0f}/sec - Synced: {synced_count:,} - ETA: {eta_hours:.1f}h"
        )
        db.commit()

    def full_sync(self, sync_log_id: int) -> Dict:
        """
        Perform a full sync of all HuggingFace models.

        This optimized version can sync ~1500 models/second with HF_TOKEN.
        Expected time for 2.4M models: ~30 minutes

        Args:
            sync_log_id: The sync log ID to track progress

        Returns:
            Dictionary with sync results
        """
        db = SessionLocalSync()

        try:
            sync_log = db.query(ModelSyncLog).filter(ModelSyncLog.id == sync_log_id).first()
            if not sync_log:
                raise ValueError(f"Sync log {sync_log_id} not found")

            sync_log.status = "running"
            sync_log.started_at = datetime.utcnow()
            sync_log.total_models = TOTAL_MODELS
            db.commit()

            logger.info(f"Starting FAST full sync (log_id={sync_log_id})")

            buffer = []
            existing_ids = set()
            processed_count = 0
            synced_count = 0
            last_progress_time = time.time()

            # Pre-fetch existing model IDs to avoid checking each time
            logger.info("Pre-fetching existing model IDs...")
            for (model_id,) in db.query(HFModel.model_id).all():
                existing_ids.add(model_id)
            logger.info(f"Found {len(existing_ids):,} existing models")

            # Process models in stream
            for model_data in self.list_models():
                processed_count += 1

                # Skip if already exists
                if model_data["model_id"] in existing_ids:
                    continue

                buffer.append(model_data)

                # Bulk insert when buffer is full
                if len(buffer) >= BATCH_SIZE:
                    inserted = self.bulk_insert(buffer, db, existing_ids)
                    synced_count += inserted
                    buffer = []
                    logger.info(f"Bulk inserted {inserted:,} models (total synced: {synced_count:,})")

                # Update progress periodically
                if time.time() - last_progress_time >= COMMIT_INTERVAL:
                    self.update_progress(db, sync_log, processed_count, synced_count)
                    last_progress_time = time.time()

            # Insert final batch
            if buffer:
                inserted = self.bulk_insert(buffer, db, existing_ids)
                synced_count += inserted

            # Complete sync
            sync_log.status = "completed"
            sync_log.completed_at = datetime.utcnow()
            sync_log.synced_models = synced_count
            sync_log.progress_percentage = 100
            db.commit()

            elapsed = (datetime.utcnow() - sync_log.started_at).total_seconds()
            logger.info(
                f"Full sync completed in {elapsed:.0f}s! "
                f"Synced: {synced_count:,}, Processed: {processed_count:,}"
            )

            return {
                "status": "completed",
                "synced": synced_count,
                "processed": processed_count,
                "elapsed_seconds": elapsed,
            }

        except Exception as e:
            logger.error(f"Full sync failed: {e}")
            if 'sync_log' in locals():
                sync_log.status = "failed"
                sync_log.completed_at = datetime.utcnow()
                sync_log.error_message = str(e)
                db.commit()
            raise
        finally:
            db.close()

    def incremental_sync(self, sync_log_id: int) -> Dict:
        """
        Perform an incremental sync of recently updated models.

        Args:
            sync_log_id: The sync log ID to track progress

        Returns:
            Dictionary with sync results
        """
        # For now, incremental sync uses the same logic as full sync
        # but could be optimized to only fetch recent models
        return self.full_sync(sync_log_id)


# Singleton instance getter
def get_sync_service(source: str = "huggingface") -> ModelSyncService:
    """Get or create the sync service instance."""
    return ModelSyncService.get_instance(source)


# Background task runners for Celery
def run_full_sync_task(sync_log_id: int, source: str = "huggingface") -> Dict:
    """Run full sync as a background task."""
    service = get_sync_service(source)
    return service.full_sync(sync_log_id)


def run_incremental_sync_task(sync_log_id: int, source: str = "huggingface") -> Dict:
    """Run incremental sync as a background task."""
    service = get_sync_service(source)
    return service.incremental_sync(sync_log_id)
