#!/usr/bin/env python
"""
Noveris AI Platform - Backend Application Entry Point

This is the main entry point for running the backend server with hot reload support.

Usage:
    # Development mode (with hot reload):
    python main.py

    # Or use uvicorn directly:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Hot Reload Features:
    - Auto-restart on code changes (.py files)
    - Fast startup (skips migrations if already at head)
    - Enabled automatically in development mode (APP_ENV=development)

Environment Variables:
    - DEBUG=true: Enable debug mode
    - DEV_AUTO_RELOAD=true: Enable hot reload
    - APP_ENV=development: Development environment
"""

import sys
from pathlib import Path

# Add Backend directory to Python path
backend_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(backend_dir))

import uvicorn

from app.core.config import settings


def main() -> None:
    """Run the FastAPI application with hot reload in development mode."""

    # Show startup info
    print("=" * 60)
    print("Starting Noveris AI Platform Backend")
    print("=" * 60)
    print(f"   Environment: {settings.app.app_env}")
    print(f"   Debug Mode: {settings.app.app_debug}")
    print(f"   Hot Reload: {settings.app.app_debug and settings.dev_auto_reload}")
    print(f"   Host: {settings.app.api_host}:{settings.app.api_port}")
    print(f"   Workers: {1 if settings.app.app_debug else settings.app.api_workers}")
    print("=" * 60)
    print()

    uvicorn.run(
        "app.main:app",
        host=settings.app.api_host,
        port=settings.app.api_port,
        reload=settings.app.app_debug and settings.dev_auto_reload,
        workers=1 if settings.app.app_debug else settings.app.api_workers,
        log_level=settings.log.level.lower(),
        access_log=settings.log.requests,
        reload_dirs=[str(backend_dir / "app")] if settings.app.app_debug else None,
        reload_delay=0.5,  # Debounce time for file changes
    )


if __name__ == "__main__":
    main()
