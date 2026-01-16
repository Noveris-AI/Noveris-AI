"""Add authorization tables

Revision ID: 20260115_1800_authz
Revises: 20260116_0200_add_chat_tables
Create Date: 2026-01-15 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260115_1800_authz'
down_revision: Union[str, None] = '20260116_0200_add_chat_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create permission effect enum
    permission_effect_enum = postgresql.ENUM('allow', 'deny', name='permission_effect', create_type=False)
    permission_effect_enum.create(op.get_bind(), checkfirst=True)

    # Create authz_modules table
    op.create_table(
        'authz_modules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('module_key', sa.String(50), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('title_i18n', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('description_i18n', sa.String(100), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('order', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('default_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('module_key'),
    )
    op.create_index('ix_authz_modules_module_key', 'authz_modules', ['module_key'])

    # Create authz_permissions table
    op.create_table(
        'authz_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('module_key', sa.String(50), nullable=False),
        sa.Column('feature', sa.String(50), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('title_i18n', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('description_i18n', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['module_key'], ['authz_modules.module_key'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index('ix_authz_permissions_key', 'authz_permissions', ['key'])
    op.create_index('ix_authz_permissions_module_key', 'authz_permissions', ['module_key'])
    op.create_index('ix_authz_permissions_module_feature', 'authz_permissions', ['module_key', 'feature'])

    # Create authz_roles table
    op.create_table(
        'authz_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('title', sa.String(100), nullable=True),
        sa.Column('title_i18n', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('description_i18n', sa.String(100), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('parent_role_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['parent_role_id'], ['authz_roles.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_authz_roles_tenant_name'),
    )
    op.create_index('ix_authz_roles_tenant_id', 'authz_roles', ['tenant_id'])
    op.create_index('ix_authz_roles_tenant_system', 'authz_roles', ['tenant_id', 'is_system'])

    # Create authz_role_permissions table
    op.create_table(
        'authz_role_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permission_key', sa.String(100), nullable=False),
        sa.Column('effect', postgresql.ENUM('allow', 'deny', name='permission_effect', create_type=False), nullable=False, server_default='allow'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['authz_roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_key'], ['authz_permissions.key'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'permission_key', name='uq_authz_role_permissions'),
    )
    op.create_index('ix_authz_role_permissions_role_id', 'authz_role_permissions', ['role_id'])
    op.create_index('ix_authz_role_permissions_permission_key', 'authz_role_permissions', ['permission_key'])
    op.create_index('ix_authz_role_permissions_effect', 'authz_role_permissions', ['effect'])

    # Create authz_user_roles table
    op.create_table(
        'authz_user_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['authz_roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'user_id', 'role_id', name='uq_authz_user_roles'),
    )
    op.create_index('ix_authz_user_roles_tenant_id', 'authz_user_roles', ['tenant_id'])
    op.create_index('ix_authz_user_roles_user_id', 'authz_user_roles', ['user_id'])
    op.create_index('ix_authz_user_roles_role_id', 'authz_user_roles', ['role_id'])
    op.create_index('ix_authz_user_roles_tenant_user', 'authz_user_roles', ['tenant_id', 'user_id'])

    # Create authz_tenant_module_settings table
    op.create_table(
        'authz_tenant_module_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('module_key', sa.String(50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['module_key'], ['authz_modules.module_key'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'module_key', name='uq_authz_tenant_module'),
    )
    op.create_index('ix_authz_tenant_module_settings_tenant_id', 'authz_tenant_module_settings', ['tenant_id'])
    op.create_index('ix_authz_tenant_module_settings_module_key', 'authz_tenant_module_settings', ['module_key'])

    # Create authz_user_permission_overrides table
    op.create_table(
        'authz_user_permission_overrides',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permission_key', sa.String(100), nullable=False),
        sa.Column('effect', postgresql.ENUM('allow', 'deny', name='permission_effect', create_type=False), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['permission_key'], ['authz_permissions.key'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'user_id', 'permission_key', name='uq_authz_user_perm_override'),
    )
    op.create_index('ix_authz_user_permission_overrides_tenant_id', 'authz_user_permission_overrides', ['tenant_id'])
    op.create_index('ix_authz_user_permission_overrides_user_id', 'authz_user_permission_overrides', ['user_id'])
    op.create_index('ix_authz_user_permission_overrides_permission_key', 'authz_user_permission_overrides', ['permission_key'])
    op.create_index('ix_authz_user_perm_override_expires', 'authz_user_permission_overrides', ['expires_at'])

    # Create authz_audit_logs table
    op.create_table(
        'authz_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_email', sa.String(255), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('resource_name', sa.String(255), nullable=True),
        sa.Column('diff', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_authz_audit_logs_tenant_id', 'authz_audit_logs', ['tenant_id'])
    op.create_index('ix_authz_audit_logs_actor_id', 'authz_audit_logs', ['actor_id'])
    op.create_index('ix_authz_audit_logs_action', 'authz_audit_logs', ['action'])
    op.create_index('ix_authz_audit_logs_resource_type', 'authz_audit_logs', ['resource_type'])
    op.create_index('ix_authz_audit_logs_created_at', 'authz_audit_logs', ['created_at'])
    op.create_index('ix_authz_audit_logs_tenant_created', 'authz_audit_logs', ['tenant_id', 'created_at'])
    op.create_index('ix_authz_audit_logs_actor_created', 'authz_audit_logs', ['actor_id', 'created_at'])

    # Create authz_policy_cache_version table
    op.create_table(
        'authz_policy_cache_version',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id'),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('authz_policy_cache_version')
    op.drop_table('authz_audit_logs')
    op.drop_table('authz_user_permission_overrides')
    op.drop_table('authz_tenant_module_settings')
    op.drop_table('authz_user_roles')
    op.drop_table('authz_role_permissions')
    op.drop_table('authz_roles')
    op.drop_table('authz_permissions')
    op.drop_table('authz_modules')

    # Drop enum type
    permission_effect_enum = postgresql.ENUM('allow', 'deny', name='permission_effect')
    permission_effect_enum.drop(op.get_bind(), checkfirst=True)
