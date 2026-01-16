"""
Celery Worker Package for Model Market Background Tasks.

This package contains the Celery application and tasks for running
model synchronization independently from the main FastAPI application.
"""

from app.worker.celery_app import celery_app

__all__ = ["celery_app"]
