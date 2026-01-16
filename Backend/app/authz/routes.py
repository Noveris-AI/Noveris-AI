"""
Authorization API routes.

Provides endpoints for managing authorization:
- Current user authorization info
- Module management
- Permission listing
- Role CRUD
- User role management
- Audit logs
- Import/Export
"""

import json
import uuid
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import (
    AuthzMeDep,
    AuthzServiceDep,
    RequirePermission,
    RequireSuperAdmin,
    UserPermissionsDep,
    get_user_authz_me,
)
from app.authz.schemas import (
    AuditLogFilter,
    AuditLogListResponse,
    AuditLogResponse,
    AuthzExport,
    AuthzImport,
    AuthzMeResponse,
    ModuleListResponse,
    ModuleResponse,
    ModuleUpdate,
    PermissionGroupResponse,
    PermissionListResponse,
    PermissionResponse,
    RoleCreate,
    RoleListResponse,
    RolePermissionsBulkUpdate,
    RoleResponse,
    RoleSummaryResponse,
    RoleUpdate,
    TenantModuleSettingResponse,
    TenantModuleSettingsBulkUpdate,
    TenantModuleSettingUpdate,
    UserListWithRolesResponse,
    UserRoleAssign,
    UserRoleResponse,
    UserWithRolesResponse,
)
from app.authz.service import AuthorizationService
from app.core.database import get_db
from app.core.dependencies import (
    ClientIpDep,
    CurrentUserDep,
    RedisDep,
    RequestIdDep,
    TenantIdDep,
    UserAgentDep,
)
from app.models.user import User

router = APIRouter(prefix="/authz", tags=["Authorization"])


# ============================================================================
# Current User Authorization
# ============================================================================


@router.get("/me", response_model=AuthzMeResponse)
async def get_me(
    authz_me: AuthzMeDep,
):
    """
    Get current user's authorization info.

    Returns enabled modules, permissions, and roles for UI gating.
    """
    return authz_me


# ============================================================================
# Module Management
# ============================================================================


@router.get(
    "/modules",
    response_model=ModuleListResponse,
    dependencies=[Depends(RequirePermission("security.module.view"))],
)
async def list_modules(
    authz_service: AuthzServiceDep,
):
    """List all modules."""
    modules = await authz_service.get_modules()
    return ModuleListResponse(
        items=[ModuleResponse.model_validate(m) for m in modules],
        total=len(modules),
    )


@router.get(
    "/modules/{module_key}",
    response_model=ModuleResponse,
    dependencies=[Depends(RequirePermission("security.module.view"))],
)
async def get_module(
    module_key: str,
    authz_service: AuthzServiceDep,
):
    """Get module by key."""
    module = await authz_service.get_module_by_key(module_key)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{module_key}' not found",
        )
    return ModuleResponse.model_validate(module)


@router.put(
    "/modules/{module_key}",
    response_model=ModuleResponse,
    dependencies=[Depends(RequireSuperAdmin())],
)
async def update_module(
    module_key: str,
    data: ModuleUpdate,
    authz_service: AuthzServiceDep,
    current_user: CurrentUserDep,
    tenant_id: TenantIdDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """Update module (super admin only)."""
    module = await authz_service.update_module(
        module_key,
        data.model_dump(exclude_unset=True),
    )
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{module_key}' not found",
        )

    # Audit log
    await authz_service.log_audit(
        tenant_id=tenant_id,
        actor_id=uuid.UUID(current_user.user_id),
        actor_email=current_user.email,
        action="module.update",
        resource_type="module",
        resource_id=module_key,
        resource_name=module.title,
        diff=data.model_dump(exclude_unset=True),
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )

    return ModuleResponse.model_validate(module)


# ============================================================================
# Tenant Module Settings
# ============================================================================


@router.get(
    "/tenant-modules",
    response_model=list[TenantModuleSettingResponse],
    dependencies=[Depends(RequirePermission("security.module.view"))],
)
async def get_tenant_module_settings(
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
):
    """Get tenant module settings."""
    settings = await authz_service.get_tenant_module_settings(tenant_id)
    modules = await authz_service.get_modules()

    result = []
    for module in modules:
        enabled = settings.get(module.module_key, module.default_enabled)
        result.append(
            TenantModuleSettingResponse(
                module_key=module.module_key,
                enabled=enabled,
                updated_at=module.updated_at,
            )
        )
    return result


@router.put(
    "/tenant-modules/{module_key}",
    response_model=TenantModuleSettingResponse,
    dependencies=[Depends(RequirePermission("security.module.manage"))],
)
async def update_tenant_module_setting(
    module_key: str,
    data: TenantModuleSettingUpdate,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    current_user: CurrentUserDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """Update tenant module setting."""
    # Verify module exists
    module = await authz_service.get_module_by_key(module_key)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{module_key}' not found",
        )

    setting = await authz_service.update_tenant_module_setting(
        tenant_id=tenant_id,
        module_key=module_key,
        enabled=data.enabled,
        updated_by=uuid.UUID(current_user.user_id),
    )

    # Audit log
    await authz_service.log_audit(
        tenant_id=tenant_id,
        actor_id=uuid.UUID(current_user.user_id),
        actor_email=current_user.email,
        action="module.enable" if data.enabled else "module.disable",
        resource_type="tenant_module",
        resource_id=module_key,
        resource_name=module.title,
        diff={"enabled": data.enabled},
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )

    return TenantModuleSettingResponse(
        module_key=module_key,
        enabled=setting.enabled,
        updated_at=setting.updated_at,
    )


@router.post(
    "/tenant-modules/bulk",
    response_model=list[TenantModuleSettingResponse],
    dependencies=[Depends(RequirePermission("security.module.manage"))],
)
async def bulk_update_tenant_module_settings(
    data: TenantModuleSettingsBulkUpdate,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    current_user: CurrentUserDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """Bulk update tenant module settings."""
    result = []

    for module_key, enabled in data.settings.items():
        module = await authz_service.get_module_by_key(module_key)
        if module is None:
            continue

        setting = await authz_service.update_tenant_module_setting(
            tenant_id=tenant_id,
            module_key=module_key,
            enabled=enabled,
            updated_by=uuid.UUID(current_user.user_id),
        )

        result.append(
            TenantModuleSettingResponse(
                module_key=module_key,
                enabled=setting.enabled,
                updated_at=setting.updated_at,
            )
        )

    # Audit log
    await authz_service.log_audit(
        tenant_id=tenant_id,
        actor_id=uuid.UUID(current_user.user_id),
        actor_email=current_user.email,
        action="module.bulk_update",
        resource_type="tenant_module",
        diff=data.settings,
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )

    return result


# ============================================================================
# Permission Management
# ============================================================================


@router.get(
    "/permissions",
    response_model=PermissionListResponse,
    dependencies=[Depends(RequirePermission("security.permission.view"))],
)
async def list_permissions(
    module_key: Optional[str] = Query(None),
    authz_service: AuthzServiceDep = None,
):
    """List all permissions."""
    permissions = await authz_service.get_permissions(module_key=module_key)
    return PermissionListResponse(
        items=[PermissionResponse.model_validate(p) for p in permissions],
        total=len(permissions),
    )


@router.get(
    "/permissions/grouped",
    response_model=list[PermissionGroupResponse],
    dependencies=[Depends(RequirePermission("security.permission.view"))],
)
async def list_permissions_grouped(
    authz_service: AuthzServiceDep,
):
    """List permissions grouped by module and feature."""
    permissions = await authz_service.get_permissions()
    modules = await authz_service.get_modules()

    # Group by module and feature
    module_map = {m.module_key: m for m in modules}
    grouped: dict[str, dict[str, list[PermissionResponse]]] = {}

    for perm in permissions:
        if perm.module_key not in grouped:
            grouped[perm.module_key] = {}
        if perm.feature not in grouped[perm.module_key]:
            grouped[perm.module_key][perm.feature] = []
        grouped[perm.module_key][perm.feature].append(
            PermissionResponse.model_validate(perm)
        )

    result = []
    for module_key, features in grouped.items():
        module = module_map.get(module_key)
        result.append(
            PermissionGroupResponse(
                module_key=module_key,
                module_title=module.title if module else module_key,
                features=features,
            )
        )

    return result


# ============================================================================
# Role Management
# ============================================================================


@router.get(
    "/roles",
    response_model=RoleListResponse,
    dependencies=[Depends(RequirePermission("security.role.view"))],
)
async def list_roles(
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    include_permissions: bool = Query(False),
):
    """List all roles for tenant."""
    roles = await authz_service.get_roles(tenant_id, include_permissions=include_permissions)

    items = []
    for role in roles:
        role_resp = RoleResponse(
            id=role.id,
            tenant_id=role.tenant_id,
            name=role.name,
            title=role.title,
            title_i18n=role.title_i18n,
            description=role.description,
            description_i18n=role.description_i18n,
            is_system=role.is_system,
            parent_role_id=role.parent_role_id,
            permissions=[
                {"permission_key": rp.permission_key, "effect": rp.effect.value, "priority": rp.priority}
                for rp in role.role_permissions
            ] if include_permissions else [],
            created_at=role.created_at,
            updated_at=role.updated_at,
        )
        items.append(role_resp)

    return RoleListResponse(items=items, total=len(items))


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(RequirePermission("security.role.view"))],
)
async def get_role(
    role_id: uuid.UUID,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
):
    """Get role by ID."""
    role = await authz_service.get_role_by_id(tenant_id, role_id, include_permissions=True)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    return RoleResponse(
        id=role.id,
        tenant_id=role.tenant_id,
        name=role.name,
        title=role.title,
        title_i18n=role.title_i18n,
        description=role.description,
        description_i18n=role.description_i18n,
        is_system=role.is_system,
        parent_role_id=role.parent_role_id,
        permissions=[
            {"permission_key": rp.permission_key, "effect": rp.effect.value, "priority": rp.priority}
            for rp in role.role_permissions
        ],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission("security.role.create"))],
)
async def create_role(
    data: RoleCreate,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    current_user: CurrentUserDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """Create a new role."""
    # Check if role with same name exists
    existing = await authz_service.get_role_by_name(tenant_id, data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{data.name}' already exists",
        )

    role = await authz_service.create_role(
        tenant_id=tenant_id,
        name=data.name,
        title=data.title,
        description=data.description,
        parent_role_id=data.parent_role_id,
        permission_keys=data.permission_keys,
    )

    # Audit log
    await authz_service.log_audit(
        tenant_id=tenant_id,
        actor_id=uuid.UUID(current_user.user_id),
        actor_email=current_user.email,
        action="role.create",
        resource_type="role",
        resource_id=str(role.id),
        resource_name=role.name,
        diff=data.model_dump(),
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )

    return RoleResponse(
        id=role.id,
        tenant_id=role.tenant_id,
        name=role.name,
        title=role.title,
        title_i18n=role.title_i18n,
        description=role.description,
        description_i18n=role.description_i18n,
        is_system=role.is_system,
        parent_role_id=role.parent_role_id,
        permissions=[],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.put(
    "/roles/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(RequirePermission("security.role.update"))],
)
async def update_role(
    role_id: uuid.UUID,
    data: RoleUpdate,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    current_user: CurrentUserDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """Update role."""
    role = await authz_service.update_role(
        tenant_id,
        role_id,
        data.model_dump(exclude_unset=True),
    )
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    # Audit log
    await authz_service.log_audit(
        tenant_id=tenant_id,
        actor_id=uuid.UUID(current_user.user_id),
        actor_email=current_user.email,
        action="role.update",
        resource_type="role",
        resource_id=str(role.id),
        resource_name=role.name,
        diff=data.model_dump(exclude_unset=True),
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )

    return RoleResponse(
        id=role.id,
        tenant_id=role.tenant_id,
        name=role.name,
        title=role.title,
        title_i18n=role.title_i18n,
        description=role.description,
        description_i18n=role.description_i18n,
        is_system=role.is_system,
        parent_role_id=role.parent_role_id,
        permissions=[],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission("security.role.delete"))],
)
async def delete_role(
    role_id: uuid.UUID,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    current_user: CurrentUserDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """Delete role (only non-system roles)."""
    role = await authz_service.get_role_by_id(tenant_id, role_id, include_permissions=False)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system role",
        )

    success = await authz_service.delete_role(tenant_id, role_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete role",
        )

    # Audit log
    await authz_service.log_audit(
        tenant_id=tenant_id,
        actor_id=uuid.UUID(current_user.user_id),
        actor_email=current_user.email,
        action="role.delete",
        resource_type="role",
        resource_id=str(role_id),
        resource_name=role.name,
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )


@router.post(
    "/roles/{role_id}/permissions",
    response_model=RoleResponse,
    dependencies=[Depends(RequirePermission("security.role.update"))],
)
async def update_role_permissions(
    role_id: uuid.UUID,
    data: RolePermissionsBulkUpdate,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    current_user: CurrentUserDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """Update role permissions (bulk add/remove)."""
    try:
        role = await authz_service.update_role_permissions(
            tenant_id=tenant_id,
            role_id=role_id,
            add=data.add,
            remove=data.remove,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Audit log
    await authz_service.log_audit(
        tenant_id=tenant_id,
        actor_id=uuid.UUID(current_user.user_id),
        actor_email=current_user.email,
        action="role.permissions.update",
        resource_type="role",
        resource_id=str(role_id),
        resource_name=role.name,
        diff={
            "add": [a.model_dump() for a in data.add] if data.add else [],
            "remove": data.remove or [],
        },
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )

    return RoleResponse(
        id=role.id,
        tenant_id=role.tenant_id,
        name=role.name,
        title=role.title,
        title_i18n=role.title_i18n,
        description=role.description,
        description_i18n=role.description_i18n,
        is_system=role.is_system,
        parent_role_id=role.parent_role_id,
        permissions=[
            {"permission_key": rp.permission_key, "effect": rp.effect.value, "priority": rp.priority}
            for rp in role.role_permissions
        ],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


# ============================================================================
# User Role Management
# ============================================================================


@router.get(
    "/users",
    response_model=UserListWithRolesResponse,
    dependencies=[Depends(RequirePermission("security.user.view"))],
)
async def list_users_with_roles(
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List users with their roles."""
    # Get users
    query = select(User).where(User.is_active == True)
    if search:
        query = query.where(
            (User.email.ilike(f"%{search}%")) | (User.name.ilike(f"%{search}%"))
        )

    # Count total
    from sqlalchemy import func as sql_func
    count_result = await db.execute(select(sql_func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    # Get paginated users
    query = query.order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    users = result.scalars().all()

    # Get roles for each user
    items = []
    for user in users:
        roles = await authz_service.get_user_roles(tenant_id, user.id)
        items.append(
            UserWithRolesResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                is_active=user.is_active,
                roles=[
                    RoleSummaryResponse(
                        id=r.id,
                        name=r.name,
                        title=r.title,
                        is_system=r.is_system,
                    )
                    for r in roles
                ],
                created_at=user.created_at,
            )
        )

    return UserListWithRolesResponse(items=items, total=total)


@router.get(
    "/users/{user_id}/roles",
    response_model=UserRoleResponse,
    dependencies=[Depends(RequirePermission("security.user.view"))],
)
async def get_user_roles(
    user_id: uuid.UUID,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
):
    """Get roles for a specific user."""
    roles = await authz_service.get_user_roles(tenant_id, user_id)
    return UserRoleResponse(
        user_id=user_id,
        roles=[
            RoleSummaryResponse(
                id=r.id,
                name=r.name,
                title=r.title,
                is_system=r.is_system,
            )
            for r in roles
        ],
    )


@router.post(
    "/users/{user_id}/roles",
    response_model=UserRoleResponse,
    dependencies=[Depends(RequirePermission("security.user.manage"))],
)
async def assign_roles_to_user(
    user_id: uuid.UUID,
    data: UserRoleAssign,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    current_user: CurrentUserDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """Assign roles to user (replaces existing roles)."""
    roles = await authz_service.assign_roles_to_user(
        tenant_id=tenant_id,
        user_id=user_id,
        role_ids=data.role_ids,
        created_by=uuid.UUID(current_user.user_id),
    )

    # Audit log
    await authz_service.log_audit(
        tenant_id=tenant_id,
        actor_id=uuid.UUID(current_user.user_id),
        actor_email=current_user.email,
        action="user.roles.assign",
        resource_type="user",
        resource_id=str(user_id),
        diff={"role_ids": [str(r) for r in data.role_ids]},
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )

    return UserRoleResponse(
        user_id=user_id,
        roles=[
            RoleSummaryResponse(
                id=r.id,
                name=r.name,
                title=r.title,
                is_system=r.is_system,
            )
            for r in roles
        ],
    )


# ============================================================================
# Audit Logs
# ============================================================================


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    dependencies=[Depends(RequirePermission("security.audit.view"))],
)
async def list_audit_logs(
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    actor_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List audit logs with filtering."""
    filter_params = AuditLogFilter(
        action=action,
        resource_type=resource_type,
        actor_id=actor_id,
    )

    logs, total = await authz_service.get_audit_logs(
        tenant_id=tenant_id,
        filter_params=filter_params,
        limit=limit,
        offset=offset,
    )

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
    )


# ============================================================================
# Import/Export
# ============================================================================


@router.get(
    "/export",
    response_model=AuthzExport,
    dependencies=[Depends(RequirePermission("security.export.execute"))],
)
async def export_authz(
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
):
    """Export authorization configuration."""
    modules = await authz_service.get_modules()
    permissions = await authz_service.get_permissions()
    roles = await authz_service.get_roles(tenant_id, include_permissions=True)
    tenant_settings = await authz_service.get_tenant_module_settings(tenant_id)

    return AuthzExport(
        modules=[ModuleResponse.model_validate(m) for m in modules],
        permissions=[PermissionResponse.model_validate(p) for p in permissions],
        roles=[
            RoleResponse(
                id=r.id,
                tenant_id=r.tenant_id,
                name=r.name,
                title=r.title,
                title_i18n=r.title_i18n,
                description=r.description,
                description_i18n=r.description_i18n,
                is_system=r.is_system,
                parent_role_id=r.parent_role_id,
                permissions=[
                    {"permission_key": rp.permission_key, "effect": rp.effect.value, "priority": rp.priority}
                    for rp in r.role_permissions
                ],
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in roles
        ],
        tenant_settings=[
            TenantModuleSettingResponse(
                module_key=key,
                enabled=enabled,
                updated_at=modules[0].updated_at if modules else None,
            )
            for key, enabled in tenant_settings.items()
        ],
    )


@router.post(
    "/import",
    dependencies=[Depends(RequirePermission("security.import.execute"))],
)
async def import_authz(
    data: AuthzImport,
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    current_user: CurrentUserDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """Import authorization configuration."""
    results = {"roles_created": 0, "settings_updated": 0}

    # Import roles
    if data.roles:
        for role_template in data.roles:
            existing = await authz_service.get_role_by_name(tenant_id, role_template.name)
            if existing:
                continue

            role = await authz_service.create_role(
                tenant_id=tenant_id,
                name=role_template.name,
                title=role_template.title,
                description=role_template.description,
            )

            # Add permissions
            if role_template.permissions:
                await authz_service.update_role_permissions(
                    tenant_id=tenant_id,
                    role_id=role.id,
                    add=role_template.permissions,
                )

            results["roles_created"] += 1

    # Import tenant settings
    if data.tenant_settings:
        for module_key, enabled in data.tenant_settings.items():
            await authz_service.update_tenant_module_setting(
                tenant_id=tenant_id,
                module_key=module_key,
                enabled=enabled,
                updated_by=uuid.UUID(current_user.user_id),
            )
            results["settings_updated"] += 1

    # Audit log
    await authz_service.log_audit(
        tenant_id=tenant_id,
        actor_id=uuid.UUID(current_user.user_id),
        actor_email=current_user.email,
        action="authz.import",
        resource_type="authz",
        diff=results,
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )

    return {"success": True, "results": results}


# ============================================================================
# Manifest Sync (Admin Only)
# ============================================================================


@router.post(
    "/sync-manifest",
    dependencies=[Depends(RequireSuperAdmin())],
)
async def sync_manifest(
    tenant_id: TenantIdDep,
    authz_service: AuthzServiceDep,
    current_user: CurrentUserDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """
    Sync modules and permissions from manifest file.

    This should be called after deployment to ensure DB is in sync with manifest.
    Super admin only.
    """
    # Load manifest
    manifest_path = Path(__file__).parent / "permissions.manifest.json"
    if not manifest_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manifest file not found",
        )

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Seed modules and permissions
    stats = await authz_service.seed_from_manifest(manifest)

    # Seed default roles for this tenant
    role_stats = await authz_service.seed_default_roles(
        tenant_id=tenant_id,
        role_templates=manifest.get("role_templates", []),
    )

    stats.update(role_stats)

    # Audit log
    await authz_service.log_audit(
        tenant_id=tenant_id,
        actor_id=uuid.UUID(current_user.user_id),
        actor_email=current_user.email,
        action="authz.sync_manifest",
        resource_type="authz",
        diff=stats,
        ip_address=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )

    return {"success": True, "stats": stats}
