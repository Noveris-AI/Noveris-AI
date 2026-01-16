"""
Celery Application Configuration for Model Market Background Tasks.

This module sets up the Celery app for running model sync tasks independently
from the main FastAPI application.
"""

import os
from celery import Celery

# Get Redis configuration
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = os.getenv("REDIS_PORT", "6379")
redis_password = os.getenv("REDIS_PASSWORD", "")
redis_db = os.getenv("REDIS_DB", "0")

# Build Redis URL for Celery broker and backend
if redis_password:
    redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
else:
    redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

# Create Celery app
celery_app = Celery(
    "noveris_model_market",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.worker.sync_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_track_started=True,
    task_time_limit=86400,  # 24 hours max for sync tasks
    task_soft_time_limit=82800,  # 23 hours soft limit
    task_acks_late=True,  # Acknowledge after task completes
    worker_prefetch_multiplier=1,  # Don't prefetch multiple tasks
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks

    # Result settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,

    # Rate limiting
    task_annotations={
        "app.worker.sync_tasks.full_sync_task": {
            "rate_limit": "1/h",  # Max 1 full sync per hour
        },
        "app.worker.sync_tasks.incremental_sync_task": {
            "rate_limit": "10/h",  # Max 10 incremental syncs per hour
        },
    },

    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Worker settings
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

# Schedule configuration - auto sync every 24 hours
celery_app.conf.beat_schedule = {
    "daily-incremental-sync": {
        "task": "app.worker.sync_tasks.scheduled_incremental_sync",
        "schedule": 86400.0,  # 24 hours in seconds
        "options": {"expires": 3600},  # Task expires after 1 hour if not picked up
    },
}

if __name__ == "__main__":
    celery_app.start()
