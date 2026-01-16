"""
Super admin initialization script.

This module handles the automatic creation of a super admin user
on application startup if configured via environment variables.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import PasswordPolicy
from app.models.user import User

logger = logging.getLogger(__name__)


async def create_super_admin(db: AsyncSession) -> None:
    """
    Create super admin user if it doesn't exist.

    This function is called on application startup. It will:
    1. Check if auto-creation is enabled (ADMIN_AUTO_CREATE)
    2. Check if a user with the admin email already exists
    3. If not, create a new super admin user with the configured credentials

    Args:
        db: Database session
    """
    # Check if auto-creation is enabled
    if not settings.admin.auto_create:
        logger.info("Super admin auto-creation is disabled (ADMIN_AUTO_CREATE=false)")
        return

    admin_email = settings.admin.email
    admin_password = settings.admin.password
    admin_name = settings.admin.name

    try:
        # Check if admin user already exists
        result = await db.execute(
            select(User).where(User.email == admin_email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.info(f"Super admin user already exists: {admin_email}")

            # Update to super admin if not already
            if not existing_user.is_superuser:
                existing_user.is_superuser = True
                await db.commit()
                logger.info(f"Updated existing user to super admin: {admin_email}")

            return

        # Create new super admin user
        hashed_password = PasswordPolicy.hash(admin_password)

        # Create default tenant ID for super admin
        default_tenant_id = UUID("00000000-0000-0000-0000-000000000001")

        new_admin = User(
            email=admin_email,
            name=admin_name,
            password_hash=hashed_password,
            is_active=True,
            is_superuser=True,
            is_verified=True,
            tenant_id=default_tenant_id,
        )

        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)

        logger.info(f"✅ Super admin user created successfully: {admin_email}")
        logger.warning(
            f"⚠️  SECURITY: Please change the default admin password immediately!\n"
            f"   Email: {admin_email}\n"
            f"   You can do this by logging in and going to Settings > Security"
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create super admin user: {e}")
        raise
