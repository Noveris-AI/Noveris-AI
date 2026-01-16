"""
Authorization dependencies for FastAPI.

Provides dependency injection for permission checking and enforcement.
"""

import uuid
from functools import wraps
from typing import Annotated, Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.authz.schemas import AuthzMeResponse, RoleSummaryResponse, UserPermissionsResponse
from app.authz.service import AuthorizationService
from app.core.database import AsyncSession, get_db
from app.core.dependencies import CurrentUserDep, RedisDep, TenantIdDep, get_current_user, get_tenant_id
from app.core.session import SessionData


# ============================================================================
# Authorization Service Dependency
# ============================================================================


async def get_authz_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: RedisDep,
) -> AuthorizationService:
    """Get authorization service instance."""
    return AuthorizationService(db, redis)


AuthzServiceDep = Annotated[AuthorizationService, Depends(get_authz_service)]


# ============================================================================
# User Permissions Dependency
# ============================================================================


async def get_user_permissions(
    current_user: CurrentUserDep,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
) -> UserPermissionsResponse:
    """
    Get current user's permissions.

    This is cached and efficient to call multiple times.
    """
    return await authz_service.get_user_permissions(
        tenant_id=tenant_id,
        user_id=uuid.UUID(current_user.user_id),
        user_email=current_user.email,
        user_name=current_user.name,
    )


UserPermissionsDep = Annotated[UserPermissionsResponse, Depends(get_user_permissions)]


# ============================================================================
# Permission Checking Dependencies
# ============================================================================


class RequirePermission:
    """
    Dependency class for requiring a specific permission.

    Usage:
        @router.get("/nodes", dependencies=[Depends(RequirePermission("node.node.view"))])
        async def list_nodes():
            ...

    Or as a dependency parameter:
        @router.get("/nodes")
        async def list_nodes(
            _: Annotated[None, Depends(RequirePermission("node.node.view"))]
        ):
            ...
    """

    def __init__(
        self,
        permission_key: str,
        module_key: Optional[str] = None,
    ):
        """
        Initialize permission requirement.

        Args:
            permission_key: Permission key to check (e.g., "node.node.view")
            module_key: Optional module key (extracted from permission_key if not provided)
        """
        self.permission_key = permission_key
        self.module_key = module_key or permission_key.split(".")[0]

    async def __call__(
        self,
        current_user: CurrentUserDep,
        tenant_id: TenantIdDep,
        authz_service: AuthzServiceDep,
    ) -> None:
        """Check permission and raise 403 if not allowed."""
        allowed, reason = await authz_service.check_permission(
            tenant_id=tenant_id,
            user_id=uuid.UUID(current_user.user_id),
            permission_key=self.permission_key,
            module_key=self.module_key,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": reason or "Permission denied",
                    "permission": self.permission_key,
                },
            )


class RequireModule:
    """
    Dependency class for requiring a module to be enabled.

    Usage:
        @router.get("/nodes", dependencies=[Depends(RequireModule("node"))])
        async def list_nodes():
            ...
    """

    def __init__(self, module_key: str):
        """Initialize module requirement."""
        self.module_key = module_key

    async def __call__(
        self,
        tenant_id: TenantIdDep,
        authz_service: AuthzServiceDep,
    ) -> None:
        """Check module enabled and raise 403 if disabled."""
        enabled = await authz_service.check_module_enabled(
            tenant_id=tenant_id,
            module_key=self.module_key,
        )

        if not enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "MODULE_DISABLED",
                    "message": f"Module '{self.module_key}' is disabled",
                    "module": self.module_key,
                },
            )


class RequireSuperAdmin:
    """
    Dependency class for requiring super admin access.

    Usage:
        @router.post("/authz/modules", dependencies=[Depends(RequireSuperAdmin())])
        async def create_module():
            ...
    """

    async def __call__(
        self,
        permissions: UserPermissionsDep,
    ) -> None:
        """Check super admin and raise 403 if not."""
        if not permissions.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "SUPER_ADMIN_REQUIRED",
                    "message": "This operation requires super admin privileges",
                },
            )


class RequireAnyPermission:
    """
    Dependency class for requiring any of multiple permissions.

    Usage:
        @router.get("/resource", dependencies=[Depends(RequireAnyPermission(["read", "admin"]))])
        async def get_resource():
            ...
    """

    def __init__(self, permission_keys: list[str]):
        """Initialize with list of permission keys."""
        self.permission_keys = permission_keys

    async def __call__(
        self,
        current_user: CurrentUserDep,
        tenant_id: TenantIdDep,
        authz_service: AuthzServiceDep,
    ) -> None:
        """Check any permission and raise 403 if none allowed."""
        for permission_key in self.permission_keys:
            allowed, _ = await authz_service.check_permission(
                tenant_id=tenant_id,
                user_id=uuid.UUID(current_user.user_id),
                permission_key=permission_key,
            )
            if allowed:
                return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PERMISSION_DENIED",
                "message": "None of the required permissions are granted",
                "permissions": self.permission_keys,
            },
        )


class RequireAllPermissions:
    """
    Dependency class for requiring all of multiple permissions.

    Usage:
        @router.post("/resource", dependencies=[Depends(RequireAllPermissions(["create", "admin"]))])
        async def create_resource():
            ...
    """

    def __init__(self, permission_keys: list[str]):
        """Initialize with list of permission keys."""
        self.permission_keys = permission_keys

    async def __call__(
        self,
        current_user: CurrentUserDep,
        tenant_id: TenantIdDep,
        authz_service: AuthzServiceDep,
    ) -> None:
        """Check all permissions and raise 403 if any not allowed."""
        for permission_key in self.permission_keys:
            allowed, reason = await authz_service.check_permission(
                tenant_id=tenant_id,
                user_id=uuid.UUID(current_user.user_id),
                permission_key=permission_key,
            )
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "PERMISSION_DENIED",
                        "message": reason or "Permission denied",
                        "permission": permission_key,
                    },
                )


# ============================================================================
# Decorator-based Permission Checking
# ============================================================================


def require_permission(permission_key: str, module_key: Optional[str] = None):
    """
    Decorator for requiring a permission on a route handler.

    Usage:
        @router.get("/nodes")
        @require_permission("node.node.view")
        async def list_nodes():
            ...

    Note: This decorator approach is less recommended than using Depends().
    The dependency approach integrates better with FastAPI's dependency injection.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from kwargs or args
            request: Request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found",
                )

            # Check permission using request state
            authz_service: AuthorizationService = request.state.authz_service
            current_user: SessionData = request.state.current_user
            tenant_id: uuid.UUID = request.state.tenant_id

            allowed, reason = await authz_service.check_permission(
                tenant_id=tenant_id,
                user_id=uuid.UUID(current_user.user_id),
                permission_key=permission_key,
                module_key=module_key,
            )

            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "PERMISSION_DENIED",
                        "message": reason or "Permission denied",
                        "permission": permission_key,
                    },
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# Super Admin Dependency (Simple)
# ============================================================================


SuperAdminDep = Annotated[None, Depends(RequireSuperAdmin())]


# ============================================================================
# Helper Functions
# ============================================================================


async def check_permission_helper(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    permission_key: str,
    db: AsyncSession,
    redis: Optional[Redis] = None,
) -> bool:
    """
    Helper function for checking permission outside of dependency context.

    Useful for checking permissions in service layer or background tasks.
    """
    service = AuthorizationService(db, redis)
    allowed, _ = await service.check_permission(
        tenant_id=tenant_id,
        user_id=user_id,
        permission_key=permission_key,
    )
    return allowed


async def get_user_authz_me(
    current_user: CurrentUserDep,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
) -> AuthzMeResponse:
    """
    Get current user's authorization info for /api/authz/me endpoint.

    This provides all information the frontend needs to gate UI elements.
    """
    perms = await authz_service.get_user_permissions(
        tenant_id=tenant_id,
        user_id=uuid.UUID(current_user.user_id),
        user_email=current_user.email,
        user_name=current_user.name,
    )

    return AuthzMeResponse(
        user_id=perms.user_id,
        tenant_id=perms.tenant_id,
        email=current_user.email,
        name=current_user.name,
        enabled_modules=perms.enabled_modules,
        permissions=perms.permissions,
        roles=perms.roles,
        is_super_admin=perms.is_super_admin,
    )


AuthzMeDep = Annotated[AuthzMeResponse, Depends(get_user_authz_me)]
