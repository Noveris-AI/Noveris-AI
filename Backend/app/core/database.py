"""
Database configuration and session management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# Create async engine
engine = create_async_engine(
    settings.database.dsn,
    echo=settings.app.app_debug,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ============================================================================
# Synchronous database (for background workers)
# ============================================================================

# Convert async DSN to sync DSN
sync_dsn = settings.database.dsn.replace(
    "postgresql+asyncpg://",
    "postgresql://",
)

# Create sync engine for background workers
sync_engine = create_engine(
    sync_dsn,
    echo=settings.app.app_debug,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
)

# Create sync session factory for background workers
SessionLocal = sessionmaker(
    sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for dependency injection.

    Yields:
        AsyncSession: Database session
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session as a context manager.

    Yields:
        AsyncSession: Database session

    Example:
        async with get_db_context() as session:
            result = await session.execute(query)
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database (create tables if they don't exist)."""
    async with engine.begin() as conn:
        # Import all models here to ensure they are registered with Base
        from app.models import user  # noqa: F401
        from app.models import node  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
