#!/usr/bin/env python
"""
Celery Beat Scheduler Entry Point.

Run this script to start the Celery Beat scheduler for 24h auto-sync:
    python beat.py

Or with Celery directly:
    celery -A app.worker.celery_app beat --loglevel=info
"""

import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.worker.celery_app import celery_app

if __name__ == "__main__":
    # Start the Celery beat scheduler
    from celery.beat import Beat
    beat = Beat(app=celery_app, loglevel="info")
    beat.start()
