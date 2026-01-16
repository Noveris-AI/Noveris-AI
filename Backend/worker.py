#!/usr/bin/env python
"""
Celery Worker Entry Point.

Run this script to start the Celery worker for model market background tasks:
    python worker.py

Or with Celery directly:
    celery -A app.worker.celery_app worker --loglevel=info --concurrency=2

For development with auto-reload:
    celery -A app.worker.celery_app worker --loglevel=info --concurrency=2 --autoscale=2,1
"""

import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.worker.celery_app import celery_app

if __name__ == "__main__":
    # Start the Celery worker
    celery_app.start()
