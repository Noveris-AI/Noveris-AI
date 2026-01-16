"""
Celery Tasks for Model Market Sync.

This module contains the Celery tasks for running model synchronization
independently from the main FastAPI application.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from app.worker.celery_app import celery_app
from app.services.model_sync_service import get_sync_service
from app.core.database import SessionLocal
from app.models.model_market import ModelSyncLog

logger = logging.getLogger(__name__)


@celery_app.task(name="app.worker.sync_tasks.full_sync_task", bind=True)
def full_sync_task(self, sync_log_id: int, source: str = "huggingface") -> Dict[str, Any]:
    """
    Execute a full model sync as a Celery task.

    This task synchronizes all models from Hugging Face Hub.

    Args:
        sync_log_id: The sync log ID to track progress
        source: Data source ("huggingface" or "hf-mirror")

    Returns:
        Dictionary with sync results
    """
    logger.info(f"Starting full sync task for sync_log_id={sync_log_id}, source={source}")

    # Update task state
    self.update_state(state="PROGRESS", meta={"status": "starting", "sync_log_id": sync_log_id})

    try:
        service = get_sync_service(source)
        result = service.full_sync(sync_log_id)

        logger.info(f"Full sync task completed for sync_log_id={sync_log_id}")
        return result

    except Exception as e:
        logger.error(f"Full sync task failed for sync_log_id={sync_log_id}: {e}")

        # Update sync log with error
        db = SessionLocal()
        try:
            sync_log = db.query(ModelSyncLog).filter(ModelSyncLog.id == sync_log_id).first()
            if sync_log:
                sync_log.status = "failed"
                sync_log.completed_at = datetime.utcnow()
                sync_log.error_message = str(e)
                db.commit()
        finally:
            db.close()

        raise


@celery_app.task(name="app.worker.sync_tasks.incremental_sync_task", bind=True)
def incremental_sync_task(self, sync_log_id: int, source: str = "huggingface") -> Dict[str, Any]:
    """
    Execute an incremental model sync as a Celery task.

    This task synchronizes only models updated since the last sync.

    Args:
        sync_log_id: The sync log ID to track progress
        source: Data source ("huggingface" or "hf-mirror")

    Returns:
        Dictionary with sync results
    """
    logger.info(f"Starting incremental sync task for sync_log_id={sync_log_id}, source={source}")

    # Update task state
    self.update_state(state="PROGRESS", meta={"status": "starting", "sync_log_id": sync_log_id})

    try:
        service = get_sync_service(source)
        result = service.incremental_sync(sync_log_id)

        logger.info(f"Incremental sync task completed for sync_log_id={sync_log_id}")
        return result

    except Exception as e:
        logger.error(f"Incremental sync task failed for sync_log_id={sync_log_id}: {e}")

        # Update sync log with error
        db = SessionLocal()
        try:
            sync_log = db.query(ModelSyncLog).filter(ModelSyncLog.id == sync_log_id).first()
            if sync_log:
                sync_log.status = "failed"
                sync_log.completed_at = datetime.utcnow()
                sync_log.error_message = str(e)
                db.commit()
        finally:
            db.close()

        raise


@celery_app.task(name="app.worker.sync_tasks.scheduled_incremental_sync")
def scheduled_incremental_sync() -> Dict[str, Any]:
    """
    Scheduled task that runs incremental sync every 24 hours.

    This task is triggered by Celery Beat and automatically syncs
    models that have been updated since the last sync.

    Returns:
        Dictionary with sync results
    """
    logger.info("Starting scheduled incremental sync (24h auto-sync)")

    db = SessionLocal()
    try:
        # Check if there's already a running sync
        running_sync = db.query(ModelSyncLog).filter(
            ModelSyncLog.status.in_(["pending", "running"])
        ).first()

        if running_sync:
            logger.info(f"Skipping scheduled sync - sync {running_sync.id} is already {running_sync.status}")
            return {"status": "skipped", "reason": "sync_already_running"}

        # Create sync log for scheduled run
        sync_log = ModelSyncLog(
            sync_type="incremental",
            status="pending",
            source="huggingface",
            triggered_by="scheduler",
        )
        db.add(sync_log)
        db.commit()
        db.refresh(sync_log)

        logger.info(f"Created sync log {sync_log.id} for scheduled sync")

        # Trigger the incremental sync task
        task = incremental_sync_task.delay(sync_log.id, "huggingface")

        return {
            "status": "triggered",
            "sync_log_id": sync_log.id,
            "celery_task_id": task.id,
        }

    except Exception as e:
        logger.error(f"Scheduled incremental sync failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.worker.sync_tasks.cancel_sync")
def cancel_sync_task(sync_log_id: int) -> Dict[str, Any]:
    """
    Cancel an ongoing sync operation.

    Args:
        sync_log_id: The sync log ID to cancel

    Returns:
        Dictionary with cancellation result
    """
    logger.info(f"Cancelling sync for sync_log_id={sync_log_id}")

    try:
        service = get_sync_service()
        service.cancel_sync(sync_log_id)

        return {"status": "cancelled", "sync_log_id": sync_log_id}

    except Exception as e:
        logger.error(f"Failed to cancel sync {sync_log_id}: {e}")
        return {"status": "error", "error": str(e)}
