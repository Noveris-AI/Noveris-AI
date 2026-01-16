"""
Authorization database models.

Implements RBAC with domains/tenants for enterprise-grade permission management.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


UTC = timezone.utc


class PermissionEffect(str, enum.Enum):
    """Permission effect enum - allow or deny."""
    ALLOW = "allow"
    DENY = "deny"


class Module(Base):
    """
    Platform module definition.

    Modules are top-level feature groupings that can be enabled/disabled.
    """
    __tablename__ = "authz_modules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    module_key: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    title_i18n: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    description_i18n: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    order: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
    )

    default_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        back_populates="module",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "module_key": self.module_key,
            "title": self.title,
            "title_i18n": self.title_i18n,
            "description": self.description,
            "icon": self.icon,
            "order": self.order,
            "default_enabled": self.default_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Permission(Base):
    """
    Permission definition.

    Permissions are individual access control points following the pattern:
    <module>.<feature>.<action>
    """
    __tablename__ = "authz_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    module_key: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("authz_modules.module_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    feature: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    title_i18n: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    description_i18n: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Metadata for UI and API mapping
    permission_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    module: Mapped["Module"] = relationship(
        "Module",
        back_populates="permissions",
    )

    __table_args__ = (
        Index("ix_authz_permissions_module_feature", "module_key", "feature"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "key": self.key,
            "module_key": self.module_key,
            "feature": self.feature,
            "action": self.action,
            "title": self.title,
            "title_i18n": self.title_i18n,
            "description": self.description,
            "metadata": self.permission_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Role(Base):
    """
    Role definition with tenant isolation.

    Roles group permissions together and can be assigned to users.
    """
    __tablename__ = "authz_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    title_i18n: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    description_i18n: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # System roles cannot be deleted
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Parent role for inheritance
    parent_role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("authz_roles.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    parent_role: Mapped[Optional["Role"]] = relationship(
        "Role",
        remote_side=[id],
        backref="child_roles",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_authz_roles_tenant_name"),
        Index("ix_authz_roles_tenant_system", "tenant_id", "is_system"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "name": self.name,
            "title": self.title,
            "title_i18n": self.title_i18n,
            "description": self.description,
            "is_system": self.is_system,
            "parent_role_id": str(self.parent_role_id) if self.parent_role_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RolePermission(Base):
    """
    Role-Permission mapping with effect (allow/deny) and priority.

    Supports explicit deny with priority-based evaluation (higher priority wins).
    """
    __tablename__ = "authz_role_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("authz_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    permission_key: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("authz_permissions.key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    effect: Mapped[PermissionEffect] = mapped_column(
        Enum(PermissionEffect),
        default=PermissionEffect.ALLOW,
        nullable=False,
    )

    # Higher priority wins in case of conflict
    priority: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="role_permissions",
    )

    __table_args__ = (
        UniqueConstraint("role_id", "permission_key", name="uq_authz_role_permissions"),
        Index("ix_authz_role_permissions_effect", "effect"),
    )


class UserRole(Base):
    """
    User-Role mapping with tenant isolation.
    """
    __tablename__ = "authz_user_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("authz_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Relationships
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="user_roles",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "role_id", name="uq_authz_user_roles"),
        Index("ix_authz_user_roles_tenant_user", "tenant_id", "user_id"),
    )


class TenantModuleSetting(Base):
    """
    Tenant-level module enable/disable settings.

    Overrides the default_enabled setting at the module level.
    """
    __tablename__ = "authz_tenant_module_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    module_key: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("authz_modules.module_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "module_key", name="uq_authz_tenant_module"),
    )


class UserPermissionOverride(Base):
    """
    User-level permission overrides.

    Allows granting or revoking specific permissions for individual users,
    optionally with an expiration time.
    """
    __tablename__ = "authz_user_permission_overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    permission_key: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("authz_permissions.key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    effect: Mapped[PermissionEffect] = mapped_column(
        Enum(PermissionEffect),
        nullable=False,
    )

    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "permission_key", name="uq_authz_user_perm_override"),
        Index("ix_authz_user_perm_override_expires", "expires_at"),
    )

    @property
    def is_expired(self) -> bool:
        """Check if override has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


class AuthzAuditLog(Base):
    """
    Audit log for authorization changes.

    Tracks all permission-related changes for compliance and debugging.
    """
    __tablename__ = "authz_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    actor_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    resource_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Before/after state for tracking changes
    diff: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    request_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_authz_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_authz_audit_logs_actor_created", "actor_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "actor_id": str(self.actor_id),
            "actor_email": self.actor_email,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "diff": self.diff,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PolicyCacheVersion(Base):
    """
    Policy cache version for invalidation.

    Used to coordinate cache invalidation across multiple instances.
    """
    __tablename__ = "authz_policy_cache_version"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
