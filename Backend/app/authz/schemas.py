"""
Pydantic schemas for authorization.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PermissionEffectEnum(str, Enum):
    """Permission effect enum."""
    ALLOW = "allow"
    DENY = "deny"


# ============================================================================
# Module Schemas
# ============================================================================


class ModuleBase(BaseModel):
    """Base module schema."""
    module_key: str = Field(..., max_length=50)
    title: str = Field(..., max_length=100)
    title_i18n: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    description_i18n: Optional[str] = Field(None, max_length=100)
    icon: Optional[str] = Field(None, max_length=50)
    order: int = Field(default=100)
    default_enabled: bool = Field(default=True)


class ModuleCreate(ModuleBase):
    """Schema for creating a module."""
    pass


class ModuleUpdate(BaseModel):
    """Schema for updating a module."""
    title: Optional[str] = Field(None, max_length=100)
    title_i18n: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    description_i18n: Optional[str] = Field(None, max_length=100)
    icon: Optional[str] = Field(None, max_length=50)
    order: Optional[int] = None
    default_enabled: Optional[bool] = None


class ModuleResponse(ModuleBase):
    """Module response schema."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModuleListResponse(BaseModel):
    """Module list response."""
    items: list[ModuleResponse]
    total: int


# ============================================================================
# Permission Schemas
# ============================================================================


class PermissionBase(BaseModel):
    """Base permission schema."""
    key: str = Field(..., max_length=100)
    module_key: str = Field(..., max_length=50)
    feature: str = Field(..., max_length=50)
    action: str = Field(..., max_length=50)
    title: str = Field(..., max_length=100)
    title_i18n: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    description_i18n: Optional[str] = Field(None, max_length=100)
    metadata: Optional[dict[str, Any]] = None


class PermissionResponse(PermissionBase):
    """Permission response schema."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PermissionListResponse(BaseModel):
    """Permission list response."""
    items: list[PermissionResponse]
    total: int


class PermissionGroupResponse(BaseModel):
    """Permissions grouped by module and feature."""
    module_key: str
    module_title: str
    features: dict[str, list[PermissionResponse]]


# ============================================================================
# Role Schemas
# ============================================================================


class RoleBase(BaseModel):
    """Base role schema."""
    name: str = Field(..., max_length=100)
    title: Optional[str] = Field(None, max_length=100)
    title_i18n: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    description_i18n: Optional[str] = Field(None, max_length=100)


class RoleCreate(RoleBase):
    """Schema for creating a role."""
    parent_role_id: Optional[UUID] = None
    permission_keys: Optional[list[str]] = None  # Initial permissions


class RoleUpdate(BaseModel):
    """Schema for updating a role."""
    name: Optional[str] = Field(None, max_length=100)
    title: Optional[str] = Field(None, max_length=100)
    title_i18n: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    description_i18n: Optional[str] = Field(None, max_length=100)
    parent_role_id: Optional[UUID] = None


class RolePermissionAssignment(BaseModel):
    """Schema for assigning permissions to a role."""
    permission_key: str
    effect: PermissionEffectEnum = PermissionEffectEnum.ALLOW
    priority: int = Field(default=100)


class RolePermissionsBulkUpdate(BaseModel):
    """Schema for bulk updating role permissions."""
    add: Optional[list[RolePermissionAssignment]] = None
    remove: Optional[list[str]] = None  # Permission keys to remove


class RolePermissionResponse(BaseModel):
    """Role permission response."""
    permission_key: str
    effect: PermissionEffectEnum
    priority: int

    class Config:
        from_attributes = True


class RoleResponse(RoleBase):
    """Role response schema."""
    id: UUID
    tenant_id: UUID
    is_system: bool
    parent_role_id: Optional[UUID]
    permissions: list[RolePermissionResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """Role list response."""
    items: list[RoleResponse]
    total: int


class RoleSummaryResponse(BaseModel):
    """Minimal role response for user lists."""
    id: UUID
    name: str
    title: Optional[str]
    is_system: bool


# ============================================================================
# User Role Schemas
# ============================================================================


class UserRoleAssign(BaseModel):
    """Schema for assigning roles to a user."""
    role_ids: list[UUID]


class UserRoleResponse(BaseModel):
    """User role response."""
    user_id: UUID
    roles: list[RoleSummaryResponse]


class UserPermissionsResponse(BaseModel):
    """Response with user's effective permissions."""
    user_id: UUID
    tenant_id: UUID
    enabled_modules: list[str]
    permissions: list[str]
    roles: list[RoleSummaryResponse]
    is_super_admin: bool = False


class UserWithRolesResponse(BaseModel):
    """User with roles response."""
    id: UUID
    email: str
    name: str
    is_active: bool
    roles: list[RoleSummaryResponse]
    created_at: datetime


class UserListWithRolesResponse(BaseModel):
    """User list with roles response."""
    items: list[UserWithRolesResponse]
    total: int


# ============================================================================
# Tenant Module Settings Schemas
# ============================================================================


class TenantModuleSettingUpdate(BaseModel):
    """Schema for updating tenant module setting."""
    enabled: bool


class TenantModuleSettingResponse(BaseModel):
    """Tenant module setting response."""
    module_key: str
    enabled: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantModuleSettingsBulkUpdate(BaseModel):
    """Schema for bulk updating tenant module settings."""
    settings: dict[str, bool]  # module_key -> enabled


# ============================================================================
# User Permission Override Schemas
# ============================================================================


class UserPermissionOverrideCreate(BaseModel):
    """Schema for creating a user permission override."""
    user_id: UUID
    permission_key: str
    effect: PermissionEffectEnum
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class UserPermissionOverrideResponse(BaseModel):
    """User permission override response."""
    id: UUID
    user_id: UUID
    permission_key: str
    effect: PermissionEffectEnum
    reason: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Audit Log Schemas
# ============================================================================


class AuditLogResponse(BaseModel):
    """Audit log response."""
    id: UUID
    tenant_id: UUID
    actor_id: UUID
    actor_email: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    resource_name: Optional[str]
    diff: Optional[dict[str, Any]]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Audit log list response."""
    items: list[AuditLogResponse]
    total: int


class AuditLogFilter(BaseModel):
    """Audit log filter parameters."""
    action: Optional[str] = None
    resource_type: Optional[str] = None
    actor_id: Optional[UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ============================================================================
# Import/Export Schemas
# ============================================================================


class RoleTemplateImport(BaseModel):
    """Schema for importing a role template."""
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    permissions: list[RolePermissionAssignment]


class AuthzExport(BaseModel):
    """Schema for exporting authorization configuration."""
    modules: list[ModuleResponse]
    permissions: list[PermissionResponse]
    roles: list[RoleResponse]
    tenant_settings: list[TenantModuleSettingResponse]


class AuthzImport(BaseModel):
    """Schema for importing authorization configuration."""
    roles: Optional[list[RoleTemplateImport]] = None
    tenant_settings: Optional[dict[str, bool]] = None  # module_key -> enabled


# ============================================================================
# Permission Check Schemas
# ============================================================================


class PermissionCheckRequest(BaseModel):
    """Schema for checking a single permission."""
    permission_key: str
    module_key: Optional[str] = None


class PermissionCheckResponse(BaseModel):
    """Permission check response."""
    allowed: bool
    permission_key: str
    reason: Optional[str] = None  # Why denied (module disabled, no permission, etc.)


class PermissionCheckBulkRequest(BaseModel):
    """Schema for checking multiple permissions."""
    permission_keys: list[str]


class PermissionCheckBulkResponse(BaseModel):
    """Bulk permission check response."""
    results: dict[str, bool]  # permission_key -> allowed


# ============================================================================
# Current User Authorization Response
# ============================================================================


class AuthzMeResponse(BaseModel):
    """Response for /api/authz/me endpoint."""
    user_id: UUID
    tenant_id: UUID
    email: str
    name: str
    enabled_modules: list[str]
    permissions: list[str]
    roles: list[RoleSummaryResponse]
    is_super_admin: bool = False
