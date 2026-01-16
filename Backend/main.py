#!/usr/bin/env python
"""
Noveris AI Platform - Backend Application Entry Point

This is the main entry point for running the backend server.
Usage:
    python main.py
    or with uvicorn directly:
    uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
"""

import sys
from pathlib import Path

# Add Backend directory to Python path
backend_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(backend_dir))

import uvicorn

from app.core.config import settings


def main() -> None:
    """Run the FastAPI application."""
    uvicorn.run(
        "app.main:app",
        host=settings.app.api_host,
        port=settings.app.api_port,
        reload=settings.app.app_debug and settings.dev_auto_reload,
        workers=1 if settings.app.app_debug else settings.app.api_workers,
        log_level=settings.log.level.lower(),
        access_log=settings.log.requests,
    )


if __name__ == "__main__":
    main()
