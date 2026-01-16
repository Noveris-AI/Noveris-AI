"""
Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import os
import threading
import multiprocessing
import subprocess
import sys
import time

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

from app.api.v1 import auth, health, models, sso, nodes, deployments
from app.api.v1.ws_events import router as ws_events_router
from app.authz.routes import router as authz_router
from app.chat.api import admin as chat_admin, public as chat_public, playground as chat_playground
from app.gateway import admin_upstreams_router, admin_api_keys_router, admin_overview_router
from app.mcp_servers.web_search_server import router as web_search_router
from app.core.config import settings
from app.core.database import close_db, init_db

# Global reference to Celery worker process
_celery_worker_process = None


def start_celery_worker():
    """Start Celery worker in a background process."""
    global _celery_worker_process

    try:
        from app.worker.celery_app import celery_app

        # Start Celery worker as a subprocess using the current Python executable
        _celery_worker_process = subprocess.Popen(
            [
                sys.executable, "-m", "celery",
                "-A", "app.worker.celery_app",
                "worker",
                "--loglevel=info",
                "--concurrency=2",
                "--max-tasks-per-child=10",
                "--pidfile=/tmp/celery_worker.pid",
            ],
            stdout=subprocess.DEVNULL,  # Suppress stdout to avoid cluttering logs
            stderr=subprocess.DEVNULL,  # Suppress stderr
            text=True,
        )
        structlog.get_logger(__name__).info(
            "Celery worker started",
            pid=_celery_worker_process.pid,
        )
    except Exception as e:
        structlog.get_logger(__name__).error(
            "Failed to start Celery worker",
            error=str(e),
        )


def stop_celery_worker():
    """Stop the Celery worker process."""
    global _celery_worker_process

    if _celery_worker_process:
        structlog.get_logger(__name__).info("Stopping Celery worker")
        _celery_worker_process.terminate()
        try:
            _celery_worker_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _celery_worker_process.kill()
        _celery_worker_process = None


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.log.format == "json" else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application", version=settings.app.app_version, env=settings.app.app_env)

    # Initialize database
    try:
        if settings.database.auto_migrate:
            logger.info("Running database migrations")
            # Use alembic from venv - fix path construction
            venv_bin = os.path.dirname(sys.executable)
            alembic_path = os.path.join(venv_bin, "alembic")
            subprocess.run([alembic_path, "upgrade", "head"], check=True)
    except Exception as e:
        logger.warning("Failed to run migrations", error=str(e))

    # Always run init_db to ensure all tables exist (idempotent - won't recreate existing tables)
    try:
        await init_db()
        logger.info("Database tables verified via init_db")
    except Exception as init_error:
        logger.error("Failed to initialize database", error=str(init_error))

    # Initialize Redis connection for WebSocket support
    if settings.redis.enabled:
        try:
            from redis.asyncio import Redis
            app.state.redis = Redis.from_url(
                settings.redis.dsn,
                encoding="utf-8",
                decode_responses=True
            )
            await app.state.redis.ping()
            logger.info("Redis connected for WebSocket support")
        except Exception as redis_err:
            logger.warning("Failed to connect Redis for WebSocket", error=str(redis_err))
            app.state.redis = None

    # Start Celery worker in background - use thread to avoid blocking
    if settings.redis.enabled:
        import threading
        threading.Thread(target=start_celery_worker, daemon=True).start()

    # Log important configuration
    logger.info(
        "Configuration loaded",
        app_name=settings.app.app_name,
        db_host=settings.database.host,
        redis_enabled=settings.redis.enabled,
        cors_origins=settings.app.cors_origins_list,
    )

    yield

    # Shutdown
    logger.info("Shutting down application")
    stop_celery_worker()

    # Close Redis connection
    if hasattr(app.state, 'redis') and app.state.redis:
        await app.state.redis.close()
        logger.info("Redis connection closed")

    await close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.app.app_name,
    version=settings.app.app_version,
    description="Noveris AI Platform - Backend API",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    lifespan=lifespan,
)


# ============================================================================
# Middleware
# ============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins_list,
    allow_credentials=settings.app.cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    """Log all requests and add request ID."""
    import uuid
    import time

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.time()

    # Log request
    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
        request_id=request_id,
    )

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        # Log response
        duration = time.time() - start_time
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
            request_id=request_id,
        )

        return response

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "Request failed",
            method=request.method,
            path=request.url.path,
            error=str(e),
            duration_ms=round(duration * 1000, 2),
            request_id=request_id,
        )
        raise


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
            },
            "meta": {
                "request_id": getattr(request.state, "request_id", None),
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """Handle validation errors."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": errors,
            },
            "meta": {
                "request_id": getattr(request.state, "request_id", None),
            },
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle general exceptions."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        error=str(exc),
        exc_info=exc,
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred" if not settings.app.app_debug else str(exc),
            },
            "meta": {
                "request_id": getattr(request.state, "request_id", None),
            },
        },
    )


# ============================================================================
# Routes
# ============================================================================

# Include API routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(sso.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")

# Node management routers
app.include_router(nodes.router, prefix="/api/v1")
app.include_router(nodes.node_groups_router, prefix="/api/v1")
app.include_router(nodes.group_vars_router, prefix="/api/v1")
app.include_router(nodes.job_templates_router, prefix="/api/v1")
app.include_router(nodes.job_runs_router, prefix="/api/v1")
app.include_router(nodes.stats_router, prefix="/api/v1")

# Model deployment router
app.include_router(deployments.router, prefix="/api/v1")

# Chat module routers
app.include_router(chat_admin.router, prefix="/api")
app.include_router(chat_public.router, prefix="/api")
app.include_router(chat_playground.router, prefix="/api")

# Authorization router
app.include_router(authz_router, prefix="/api/v1")

# AI Gateway control plane routers
app.include_router(admin_upstreams_router)
app.include_router(admin_api_keys_router)
app.include_router(admin_overview_router)

# MCP server routers
app.include_router(web_search_router, prefix="/api/mcp")

# WebSocket routers for real-time events
app.include_router(ws_events_router, prefix="/api/v1")
