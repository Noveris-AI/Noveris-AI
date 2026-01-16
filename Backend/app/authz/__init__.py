"""
Authorization module for Noveris AI Platform.

This module implements RBAC with domains/tenants using Casbin.
"""

from app.authz.models import (
    Module,
    Permission,
    Role,
    RolePermission,
    UserRole,
    TenantModuleSetting,
    UserPermissionOverride,
    AuthzAuditLog,
    PolicyCacheVersion,
    PermissionEffect,
)
from app.authz.service import AuthorizationService
from app.authz.dependencies import (
    AuthzServiceDep,
    RequirePermission,
    RequireModule,
    RequireSuperAdmin,
    RequireAnyPermission,
    RequireAllPermissions,
    UserPermissionsDep,
    AuthzMeDep,
)
from app.authz.routes import router as authz_router

__all__ = [
    # Models
    "Module",
    "Permission",
    "Role",
    "RolePermission",
    "UserRole",
    "TenantModuleSetting",
    "UserPermissionOverride",
    "AuthzAuditLog",
    "PolicyCacheVersion",
    "PermissionEffect",
    # Service
    "AuthorizationService",
    # Dependencies
    "AuthzServiceDep",
    "RequirePermission",
    "RequireModule",
    "RequireSuperAdmin",
    "RequireAnyPermission",
    "RequireAllPermissions",
    "UserPermissionsDep",
    "AuthzMeDep",
    # Router
    "authz_router",
]
