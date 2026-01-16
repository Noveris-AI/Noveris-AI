"""
Authorization service.

Provides permission computation, caching, and enforcement.
"""

import fnmatch
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Set, Tuple

from redis.asyncio import Redis
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.authz.models import (
    AuthzAuditLog,
    Module,
    Permission,
    PermissionEffect,
    PolicyCacheVersion,
    Role,
    RolePermission,
    TenantModuleSetting,
    UserPermissionOverride,
    UserRole,
)
from app.authz.schemas import (
    AuditLogFilter,
    AuthzMeResponse,
    PermissionEffectEnum,
    RolePermissionAssignment,
    RoleSummaryResponse,
    UserPermissionsResponse,
)

UTC = timezone.utc

# Redis cache key patterns
CACHE_PREFIX = "authz"
CACHE_TTL = 300  # 5 minutes


class AuthorizationService:
    """
    Service for authorization management and enforcement.

    Provides:
    - Permission computation with caching
    - Role management
    - Module management
    - Audit logging
    """

    def __init__(self, db: AsyncSession, redis: Optional[Redis] = None):
        self.db = db
        self.redis = redis

    # ========================================================================
    # Cache Management
    # ========================================================================

    def _cache_key(self, tenant_id: uuid.UUID, user_id: uuid.UUID, version: int) -> str:
        """Generate cache key for user permissions."""
        return f"{CACHE_PREFIX}:perm:{tenant_id}:{user_id}:{version}"

    def _version_key(self, tenant_id: uuid.UUID) -> str:
        """Generate cache key for policy version."""
        return f"{CACHE_PREFIX}:version:{tenant_id}"

    async def _get_cache_version(self, tenant_id: uuid.UUID) -> int:
        """Get current cache version for tenant."""
        if not self.redis:
            return 0

        cached = await self.redis.get(self._version_key(tenant_id))
        if cached:
            return int(cached)

        # Check database
        result = await self.db.execute(
            select(PolicyCacheVersion).where(PolicyCacheVersion.tenant_id == tenant_id)
        )
        version_row = result.scalar_one_or_none()

        if version_row:
            version = version_row.version
        else:
            # Create initial version
            version_row = PolicyCacheVersion(tenant_id=tenant_id, version=1)
            self.db.add(version_row)
            await self.db.commit()
            version = 1

        # Cache the version
        await self.redis.set(self._version_key(tenant_id), version, ex=CACHE_TTL)
        return version

    async def _increment_cache_version(self, tenant_id: uuid.UUID) -> int:
        """Increment cache version to invalidate caches."""
        # Update database
        result = await self.db.execute(
            update(PolicyCacheVersion)
            .where(PolicyCacheVersion.tenant_id == tenant_id)
            .values(version=PolicyCacheVersion.version + 1)
            .returning(PolicyCacheVersion.version)
        )
        row = result.scalar_one_or_none()

        if row is None:
            # Create initial version
            version_row = PolicyCacheVersion(tenant_id=tenant_id, version=1)
            self.db.add(version_row)
            await self.db.commit()
            new_version = 1
        else:
            await self.db.commit()
            new_version = row

        # Update Redis
        if self.redis:
            await self.redis.set(self._version_key(tenant_id), new_version, ex=CACHE_TTL)
            # Delete all cached permissions for this tenant (pattern delete)
            async for key in self.redis.scan_iter(f"{CACHE_PREFIX}:perm:{tenant_id}:*"):
                await self.redis.delete(key)

        return new_version

    async def _get_cached_permissions(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[UserPermissionsResponse]:
        """Get cached user permissions."""
        if not self.redis:
            return None

        version = await self._get_cache_version(tenant_id)
        key = self._cache_key(tenant_id, user_id, version)
        cached = await self.redis.get(key)

        if cached:
            data = json.loads(cached)
            return UserPermissionsResponse(**data)

        return None

    async def _cache_permissions(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        permissions: UserPermissionsResponse,
    ) -> None:
        """Cache user permissions."""
        if not self.redis:
            return

        version = await self._get_cache_version(tenant_id)
        key = self._cache_key(tenant_id, user_id, version)
        data = permissions.model_dump(mode="json")
        await self.redis.set(key, json.dumps(data), ex=CACHE_TTL)

    # ========================================================================
    # Permission Computation
    # ========================================================================

    async def get_user_permissions(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        user_email: str = "",
        user_name: str = "",
    ) -> UserPermissionsResponse:
        """
        Compute effective permissions for a user.

        This includes:
        - Module enable/disable status
        - Role-based permissions (with inheritance)
        - User-level permission overrides
        - Super admin detection
        """
        # Check cache first
        cached = await self._get_cached_permissions(tenant_id, user_id)
        if cached:
            return cached

        # Check if user is super admin from User table first
        from app.models.user import User
        import structlog
        logger = structlog.get_logger(__name__)

        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        is_super_admin = user.is_superuser if user else False

        logger.info(
            "Checking super admin status",
            user_id=str(user_id),
            user_email=user.email if user else None,
            is_superuser=user.is_superuser if user else None,
            is_super_admin=is_super_admin,
        )

        # Get user's roles with permissions
        roles_result = await self.db.execute(
            select(UserRole)
            .where(UserRole.tenant_id == tenant_id, UserRole.user_id == user_id)
            .options(selectinload(UserRole.role).selectinload(Role.role_permissions))
        )
        user_roles = roles_result.scalars().all()

        # Build role summaries and also check for super_admin role
        role_summaries = []

        for ur in user_roles:
            role = ur.role
            role_summaries.append(
                RoleSummaryResponse(
                    id=role.id,
                    name=role.name,
                    title=role.title,
                    is_system=role.is_system,
                )
            )
            if role.name == "super_admin":
                is_super_admin = True

        # Get enabled modules for tenant
        enabled_modules = await self._get_enabled_modules(tenant_id)

        # If super admin, return all permissions
        if is_super_admin:
            all_permissions = await self._get_all_permission_keys()
            result = UserPermissionsResponse(
                user_id=user_id,
                tenant_id=tenant_id,
                enabled_modules=list(enabled_modules),
                permissions=all_permissions,
                roles=role_summaries,
                is_super_admin=True,
            )
            await self._cache_permissions(tenant_id, user_id, result)
            return result

        # Compute permissions from roles
        permission_map: dict[str, Tuple[PermissionEffect, int]] = {}

        for ur in user_roles:
            role = ur.role

            # Handle role inheritance
            role_chain = await self._get_role_chain(role)

            for r in role_chain:
                for rp in r.role_permissions:
                    existing = permission_map.get(rp.permission_key)
                    if existing is None or rp.priority > existing[1]:
                        permission_map[rp.permission_key] = (rp.effect, rp.priority)

        # Apply user-level overrides
        overrides_result = await self.db.execute(
            select(UserPermissionOverride).where(
                UserPermissionOverride.tenant_id == tenant_id,
                UserPermissionOverride.user_id == user_id,
            )
        )
        overrides = overrides_result.scalars().all()

        for override in overrides:
            if override.is_expired:
                continue
            # User overrides have highest priority (1000)
            permission_map[override.permission_key] = (override.effect, 1000)

        # Filter to allowed permissions
        allowed_permissions = [
            key for key, (effect, _) in permission_map.items()
            if effect == PermissionEffect.ALLOW
        ]

        # Filter by enabled modules
        final_permissions = []
        for perm_key in allowed_permissions:
            module_key = perm_key.split(".")[0]
            if module_key in enabled_modules:
                final_permissions.append(perm_key)

        result = UserPermissionsResponse(
            user_id=user_id,
            tenant_id=tenant_id,
            enabled_modules=list(enabled_modules),
            permissions=final_permissions,
            roles=role_summaries,
            is_super_admin=False,
        )

        await self._cache_permissions(tenant_id, user_id, result)
        return result

    async def _get_role_chain(self, role: Role) -> list[Role]:
        """Get role inheritance chain (role + all parent roles)."""
        chain = [role]
        current = role

        while current.parent_role_id:
            result = await self.db.execute(
                select(Role)
                .where(Role.id == current.parent_role_id)
                .options(selectinload(Role.role_permissions))
            )
            parent = result.scalar_one_or_none()
            if parent is None:
                break
            chain.append(parent)
            current = parent

        return chain

    async def _get_enabled_modules(self, tenant_id: uuid.UUID) -> Set[str]:
        """Get set of enabled module keys for tenant."""
        # Get all modules with their defaults
        modules_result = await self.db.execute(select(Module))
        modules = modules_result.scalars().all()

        # Get tenant overrides
        overrides_result = await self.db.execute(
            select(TenantModuleSetting).where(
                TenantModuleSetting.tenant_id == tenant_id
            )
        )
        overrides = {o.module_key: o.enabled for o in overrides_result.scalars().all()}

        # Compute final enabled modules
        enabled = set()
        for module in modules:
            if module.module_key in overrides:
                if overrides[module.module_key]:
                    enabled.add(module.module_key)
            elif module.default_enabled:
                enabled.add(module.module_key)

        return enabled

    async def _get_all_permission_keys(self) -> list[str]:
        """Get all permission keys."""
        result = await self.db.execute(select(Permission.key))
        return [row[0] for row in result.all()]

    # ========================================================================
    # Permission Checking
    # ========================================================================

    async def check_permission(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        permission_key: str,
        module_key: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user has a specific permission.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            permission_key: Permission key to check
            module_key: Optional module key (extracted from permission_key if not provided)

        Returns:
            Tuple of (allowed, reason)
        """
        # Get user permissions
        perms = await self.get_user_permissions(tenant_id, user_id)

        # Super admin has all permissions
        if perms.is_super_admin:
            return True, None

        # Check module enabled
        if module_key is None:
            module_key = permission_key.split(".")[0]

        if module_key not in perms.enabled_modules:
            return False, f"Module '{module_key}' is disabled"

        # Check permission
        if permission_key in perms.permissions:
            return True, None

        # Check wildcard permissions
        for perm in perms.permissions:
            if self._match_permission(perm, permission_key):
                return True, None

        return False, "Permission denied"

    def _match_permission(self, pattern: str, permission: str) -> bool:
        """Match permission with wildcard support."""
        # Direct match
        if pattern == permission:
            return True

        # Wildcard match (e.g., "node.*" matches "node.node.view")
        if "*" in pattern:
            return fnmatch.fnmatch(permission, pattern)

        return False

    async def check_module_enabled(
        self,
        tenant_id: uuid.UUID,
        module_key: str,
    ) -> bool:
        """Check if a module is enabled for tenant."""
        enabled_modules = await self._get_enabled_modules(tenant_id)
        return module_key in enabled_modules

    # ========================================================================
    # Module Management
    # ========================================================================

    async def get_modules(self) -> list[Module]:
        """Get all modules."""
        result = await self.db.execute(
            select(Module).order_by(Module.order, Module.module_key)
        )
        return list(result.scalars().all())

    async def get_module_by_key(self, module_key: str) -> Optional[Module]:
        """Get module by key."""
        result = await self.db.execute(
            select(Module).where(Module.module_key == module_key)
        )
        return result.scalar_one_or_none()

    async def update_module(
        self,
        module_key: str,
        data: dict[str, Any],
    ) -> Optional[Module]:
        """Update module."""
        result = await self.db.execute(
            select(Module).where(Module.module_key == module_key)
        )
        module = result.scalar_one_or_none()
        if module is None:
            return None

        for key, value in data.items():
            if hasattr(module, key) and value is not None:
                setattr(module, key, value)

        await self.db.commit()
        await self.db.refresh(module)
        return module

    async def get_tenant_module_settings(
        self,
        tenant_id: uuid.UUID,
    ) -> dict[str, bool]:
        """Get tenant module settings."""
        result = await self.db.execute(
            select(TenantModuleSetting).where(
                TenantModuleSetting.tenant_id == tenant_id
            )
        )
        return {s.module_key: s.enabled for s in result.scalars().all()}

    async def update_tenant_module_setting(
        self,
        tenant_id: uuid.UUID,
        module_key: str,
        enabled: bool,
        updated_by: Optional[uuid.UUID] = None,
    ) -> TenantModuleSetting:
        """Update tenant module setting."""
        result = await self.db.execute(
            select(TenantModuleSetting).where(
                TenantModuleSetting.tenant_id == tenant_id,
                TenantModuleSetting.module_key == module_key,
            )
        )
        setting = result.scalar_one_or_none()

        if setting is None:
            setting = TenantModuleSetting(
                tenant_id=tenant_id,
                module_key=module_key,
                enabled=enabled,
                updated_by=updated_by,
            )
            self.db.add(setting)
        else:
            setting.enabled = enabled
            setting.updated_by = updated_by

        await self.db.commit()
        await self._increment_cache_version(tenant_id)
        return setting

    # ========================================================================
    # Permission Management
    # ========================================================================

    async def get_permissions(
        self,
        module_key: Optional[str] = None,
    ) -> list[Permission]:
        """Get all permissions, optionally filtered by module."""
        query = select(Permission).order_by(Permission.module_key, Permission.feature, Permission.action)
        if module_key:
            query = query.where(Permission.module_key == module_key)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_permission_by_key(self, key: str) -> Optional[Permission]:
        """Get permission by key."""
        result = await self.db.execute(
            select(Permission).where(Permission.key == key)
        )
        return result.scalar_one_or_none()

    # ========================================================================
    # Role Management
    # ========================================================================

    async def get_roles(
        self,
        tenant_id: uuid.UUID,
        include_permissions: bool = False,
    ) -> list[Role]:
        """Get all roles for tenant."""
        query = select(Role).where(Role.tenant_id == tenant_id).order_by(Role.is_system.desc(), Role.name)
        if include_permissions:
            query = query.options(selectinload(Role.role_permissions))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_role_by_id(
        self,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID,
        include_permissions: bool = True,
    ) -> Optional[Role]:
        """Get role by ID."""
        query = select(Role).where(Role.tenant_id == tenant_id, Role.id == role_id)
        if include_permissions:
            query = query.options(selectinload(Role.role_permissions))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_role_by_name(
        self,
        tenant_id: uuid.UUID,
        name: str,
    ) -> Optional[Role]:
        """Get role by name."""
        result = await self.db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.name == name)
        )
        return result.scalar_one_or_none()

    async def create_role(
        self,
        tenant_id: uuid.UUID,
        name: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        parent_role_id: Optional[uuid.UUID] = None,
        permission_keys: Optional[list[str]] = None,
        is_system: bool = False,
    ) -> Role:
        """Create a new role."""
        role = Role(
            tenant_id=tenant_id,
            name=name,
            title=title or name,
            description=description,
            parent_role_id=parent_role_id,
            is_system=is_system,
        )
        self.db.add(role)
        await self.db.flush()

        # Add initial permissions
        if permission_keys:
            for key in permission_keys:
                rp = RolePermission(
                    role_id=role.id,
                    permission_key=key,
                    effect=PermissionEffect.ALLOW.value,
                )
                self.db.add(rp)

        await self.db.commit()
        await self._increment_cache_version(tenant_id)
        return role

    async def update_role(
        self,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID,
        data: dict[str, Any],
    ) -> Optional[Role]:
        """Update role."""
        role = await self.get_role_by_id(tenant_id, role_id, include_permissions=False)
        if role is None:
            return None

        if role.is_system:
            # System roles can only update title and description
            allowed_fields = {"title", "description", "title_i18n", "description_i18n"}
            data = {k: v for k, v in data.items() if k in allowed_fields}

        for key, value in data.items():
            if hasattr(role, key) and value is not None:
                setattr(role, key, value)

        await self.db.commit()
        await self._increment_cache_version(tenant_id)
        return role

    async def delete_role(
        self,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> bool:
        """Delete role (only non-system roles)."""
        role = await self.get_role_by_id(tenant_id, role_id, include_permissions=False)
        if role is None or role.is_system:
            return False

        await self.db.delete(role)
        await self.db.commit()
        await self._increment_cache_version(tenant_id)
        return True

    async def update_role_permissions(
        self,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID,
        add: Optional[list[RolePermissionAssignment]] = None,
        remove: Optional[list[str]] = None,
    ) -> Role:
        """Update role permissions."""
        role = await self.get_role_by_id(tenant_id, role_id, include_permissions=True)
        if role is None:
            raise ValueError("Role not found")

        # Remove permissions
        if remove:
            await self.db.execute(
                delete(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_key.in_(remove),
                )
            )

        # Add permissions
        if add:
            existing_keys = {rp.permission_key for rp in role.role_permissions}
            for assignment in add:
                if assignment.permission_key not in existing_keys:
                    rp = RolePermission(
                        role_id=role_id,
                        permission_key=assignment.permission_key,
                        effect=PermissionEffect(assignment.effect.value),
                        priority=assignment.priority,
                    )
                    self.db.add(rp)
                else:
                    # Update existing
                    await self.db.execute(
                        update(RolePermission)
                        .where(
                            RolePermission.role_id == role_id,
                            RolePermission.permission_key == assignment.permission_key,
                        )
                        .values(
                            effect=PermissionEffect(assignment.effect.value),
                            priority=assignment.priority,
                        )
                    )

        await self.db.commit()
        await self._increment_cache_version(tenant_id)

        # Refresh role
        return await self.get_role_by_id(tenant_id, role_id, include_permissions=True)

    # ========================================================================
    # User Role Management
    # ========================================================================

    async def get_user_roles(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[Role]:
        """Get roles for a user."""
        result = await self.db.execute(
            select(UserRole)
            .where(UserRole.tenant_id == tenant_id, UserRole.user_id == user_id)
            .options(selectinload(UserRole.role))
        )
        return [ur.role for ur in result.scalars().all()]

    async def assign_roles_to_user(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        role_ids: list[uuid.UUID],
        created_by: Optional[uuid.UUID] = None,
    ) -> list[Role]:
        """Assign roles to user (replaces existing roles)."""
        # Delete existing roles
        await self.db.execute(
            delete(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.user_id == user_id,
            )
        )

        # Add new roles
        for role_id in role_ids:
            ur = UserRole(
                tenant_id=tenant_id,
                user_id=user_id,
                role_id=role_id,
                created_by=created_by,
            )
            self.db.add(ur)

        await self.db.commit()
        await self._increment_cache_version(tenant_id)

        return await self.get_user_roles(tenant_id, user_id)

    async def add_role_to_user(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        created_by: Optional[uuid.UUID] = None,
    ) -> bool:
        """Add a single role to user."""
        # Check if already assigned
        result = await self.db.execute(
            select(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
            )
        )
        if result.scalar_one_or_none():
            return False

        ur = UserRole(
            tenant_id=tenant_id,
            user_id=user_id,
            role_id=role_id,
            created_by=created_by,
        )
        self.db.add(ur)
        await self.db.commit()
        await self._increment_cache_version(tenant_id)
        return True

    async def remove_role_from_user(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> bool:
        """Remove a single role from user."""
        result = await self.db.execute(
            delete(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
            )
        )
        await self.db.commit()
        await self._increment_cache_version(tenant_id)
        return result.rowcount > 0

    # ========================================================================
    # Audit Logging
    # ========================================================================

    async def log_audit(
        self,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_email: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        diff: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> AuthzAuditLog:
        """Create an audit log entry."""
        log = AuthzAuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            diff=diff,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        self.db.add(log)
        await self.db.commit()
        return log

    async def get_audit_logs(
        self,
        tenant_id: uuid.UUID,
        filter_params: Optional[AuditLogFilter] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[list[AuthzAuditLog], int]:
        """Get audit logs with filtering."""
        query = select(AuthzAuditLog).where(AuthzAuditLog.tenant_id == tenant_id)
        count_query = select(AuthzAuditLog).where(AuthzAuditLog.tenant_id == tenant_id)

        if filter_params:
            if filter_params.action:
                query = query.where(AuthzAuditLog.action == filter_params.action)
                count_query = count_query.where(AuthzAuditLog.action == filter_params.action)
            if filter_params.resource_type:
                query = query.where(AuthzAuditLog.resource_type == filter_params.resource_type)
                count_query = count_query.where(AuthzAuditLog.resource_type == filter_params.resource_type)
            if filter_params.actor_id:
                query = query.where(AuthzAuditLog.actor_id == filter_params.actor_id)
                count_query = count_query.where(AuthzAuditLog.actor_id == filter_params.actor_id)
            if filter_params.start_date:
                query = query.where(AuthzAuditLog.created_at >= filter_params.start_date)
                count_query = count_query.where(AuthzAuditLog.created_at >= filter_params.start_date)
            if filter_params.end_date:
                query = query.where(AuthzAuditLog.created_at <= filter_params.end_date)
                count_query = count_query.where(AuthzAuditLog.created_at <= filter_params.end_date)

        # Count total
        from sqlalchemy import func as sql_func
        count_result = await self.db.execute(select(sql_func.count()).select_from(count_query.subquery()))
        total = count_result.scalar()

        # Get paginated results
        query = query.order_by(AuthzAuditLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)

        return list(result.scalars().all()), total

    # ========================================================================
    # Manifest Seeding
    # ========================================================================

    async def seed_from_manifest(self, manifest: dict) -> dict[str, int]:
        """
        Seed modules and permissions from manifest.

        Returns counts of created/updated items.
        """
        stats = {"modules_created": 0, "modules_updated": 0, "permissions_created": 0, "permissions_updated": 0}

        # Seed modules
        for module_data in manifest.get("modules", []):
            result = await self.db.execute(
                select(Module).where(Module.module_key == module_data["module_key"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update
                for key in ["title", "title_i18n", "description", "description_i18n", "icon", "order", "default_enabled"]:
                    if key in module_data:
                        setattr(existing, key, module_data[key])
                stats["modules_updated"] += 1
            else:
                # Create
                module = Module(
                    module_key=module_data["module_key"],
                    title=module_data.get("title", module_data["module_key"]),
                    title_i18n=module_data.get("title_i18n"),
                    description=module_data.get("description"),
                    description_i18n=module_data.get("description_i18n"),
                    icon=module_data.get("icon"),
                    order=module_data.get("order", 100),
                    default_enabled=module_data.get("default_enabled", True),
                )
                self.db.add(module)
                stats["modules_created"] += 1

        await self.db.flush()

        # Seed permissions
        for perm_data in manifest.get("permissions", []):
            result = await self.db.execute(
                select(Permission).where(Permission.key == perm_data["key"])
            )
            existing = result.scalar_one_or_none()

            metadata = {}
            if "ui" in perm_data:
                metadata["ui"] = perm_data["ui"]
            if "api" in perm_data:
                metadata["api"] = perm_data["api"]

            if existing:
                # Update
                existing.module_key = perm_data["module_key"]
                existing.feature = perm_data["feature"]
                existing.action = perm_data["action"]
                existing.title = perm_data.get("title", perm_data["key"])
                existing.title_i18n = perm_data.get("title_i18n")
                existing.description = perm_data.get("description")
                existing.description_i18n = perm_data.get("description_i18n")
                existing.permission_metadata = metadata
                stats["permissions_updated"] += 1
            else:
                # Create
                permission = Permission(
                    key=perm_data["key"],
                    module_key=perm_data["module_key"],
                    feature=perm_data["feature"],
                    action=perm_data["action"],
                    title=perm_data.get("title", perm_data["key"]),
                    title_i18n=perm_data.get("title_i18n"),
                    description=perm_data.get("description"),
                    description_i18n=perm_data.get("description_i18n"),
                    permission_metadata=metadata,
                )
                self.db.add(permission)
                stats["permissions_created"] += 1

        await self.db.commit()
        return stats

    async def seed_default_roles(
        self,
        tenant_id: uuid.UUID,
        role_templates: list[dict],
    ) -> dict[str, int]:
        """
        Seed default roles from templates.

        Returns counts of created roles.
        """
        stats = {"roles_created": 0, "roles_updated": 0}

        for template in role_templates:
            # Check if role exists
            existing = await self.get_role_by_name(tenant_id, template["name"])

            if existing:
                # Don't modify existing roles
                stats["roles_updated"] += 1
                continue

            # Create role
            role = await self.create_role(
                tenant_id=tenant_id,
                name=template["name"],
                title=template.get("title", template["name"]),
                description=template.get("description"),
                is_system=template.get("is_system", False),
            )

            # Add permissions
            included = template.get("included_permissions", [])
            excluded = template.get("excluded_permissions", [])

            # Get all permission keys
            all_keys = await self._get_all_permission_keys()

            # Expand wildcards
            permission_keys = set()
            for pattern in included:
                if pattern == "*":
                    permission_keys.update(all_keys)
                elif "*" in pattern:
                    for key in all_keys:
                        if fnmatch.fnmatch(key, pattern):
                            permission_keys.add(key)
                else:
                    permission_keys.add(pattern)

            # Remove excluded
            for pattern in excluded:
                if "*" in pattern:
                    permission_keys = {k for k in permission_keys if not fnmatch.fnmatch(k, pattern)}
                else:
                    permission_keys.discard(pattern)

            # Add to role
            for key in permission_keys:
                rp = RolePermission(
                    role_id=role.id,
                    permission_key=key,
                    effect=PermissionEffect.ALLOW.value,
                )
                self.db.add(rp)

            stats["roles_created"] += 1

        await self.db.commit()
        return stats
