"""Add settings and SSO tables

Revision ID: 20260117_0001_settings
Revises: 20260115_1800_authz
Create Date: 2026-01-17 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260117_0001_settings'
down_revision: Union[str, None] = '20260115_1800_authz'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create scope_type enum
    scope_type_enum = postgresql.ENUM(
        'system', 'tenant', 'user',
        name='settings_scope_type',
        create_type=False
    )
    scope_type_enum.create(op.get_bind(), checkfirst=True)

    # Create auth_domain enum
    auth_domain_enum = postgresql.ENUM(
        'admin', 'members', 'webapp',
        name='auth_domain_type',
        create_type=False
    )
    auth_domain_enum.create(op.get_bind(), checkfirst=True)

    # Create sso_provider_type enum
    sso_provider_type_enum = postgresql.ENUM(
        'saml', 'oidc', 'oauth2',
        name='sso_provider_type',
        create_type=False
    )
    sso_provider_type_enum.create(op.get_bind(), checkfirst=True)

    # Create notification_channel_type enum
    notification_channel_type_enum = postgresql.ENUM(
        'smtp', 'webhook', 'slack', 'feishu', 'wecom', 'dingtalk',
        name='notification_channel_type',
        create_type=False
    )
    notification_channel_type_enum.create(op.get_bind(), checkfirst=True)

    # ==========================================
    # 1. settings_kv - Universal settings key-value store
    # ==========================================
    op.create_table(
        'settings_kv',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_type', postgresql.ENUM('system', 'tenant', 'user', name='settings_scope_type', create_type=False), nullable=False),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),  # NULL for system scope
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('value_json', postgresql.JSONB(), nullable=True),
        sa.Column('value_enc', sa.LargeBinary(), nullable=True),  # Encrypted value
        sa.Column('is_encrypted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope_type', 'scope_id', 'key', name='uq_settings_kv_scope_key'),
    )
    op.create_index('ix_settings_kv_scope_type', 'settings_kv', ['scope_type'])
    op.create_index('ix_settings_kv_scope_id', 'settings_kv', ['scope_id'])
    op.create_index('ix_settings_kv_key', 'settings_kv', ['key'])
    op.create_index('ix_settings_kv_scope_key', 'settings_kv', ['scope_type', 'scope_id', 'key'])

    # ==========================================
    # 2. sso_providers - SSO Identity Providers
    # ==========================================
    op.create_table(
        'sso_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_type', postgresql.ENUM('system', 'tenant', 'user', name='settings_scope_type', create_type=False), nullable=False, server_default='system'),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),  # NULL for system scope
        sa.Column('domain', postgresql.ENUM('admin', 'members', 'webapp', name='auth_domain_type', create_type=False), nullable=False, server_default='admin'),
        sa.Column('provider_type', postgresql.ENUM('saml', 'oidc', 'oauth2', name='sso_provider_type', create_type=False), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),  # Icon identifier for UI
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('order', sa.Integer(), nullable=False, server_default='100'),  # Sort order
        # Non-sensitive configuration (stored as JSON)
        sa.Column('config_json', postgresql.JSONB(), nullable=True),
        # Encrypted secrets (client_secret, certificates, etc.)
        sa.Column('secrets_enc', sa.LargeBinary(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope_type', 'scope_id', 'domain', 'name', name='uq_sso_providers_scope_domain_name'),
    )
    op.create_index('ix_sso_providers_scope_type', 'sso_providers', ['scope_type'])
    op.create_index('ix_sso_providers_scope_id', 'sso_providers', ['scope_id'])
    op.create_index('ix_sso_providers_domain', 'sso_providers', ['domain'])
    op.create_index('ix_sso_providers_provider_type', 'sso_providers', ['provider_type'])
    op.create_index('ix_sso_providers_enabled', 'sso_providers', ['enabled'])

    # ==========================================
    # 3. auth_policies - Authentication Policies per domain
    # ==========================================
    op.create_table(
        'auth_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('domain', postgresql.ENUM('admin', 'members', 'webapp', name='auth_domain_type', create_type=False), nullable=False),
        sa.Column('scope_type', postgresql.ENUM('system', 'tenant', 'user', name='settings_scope_type', create_type=False), nullable=False, server_default='system'),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),  # NULL for system scope
        # Login methods
        sa.Column('email_password_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_code_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sso_enabled', sa.Boolean(), nullable=False, server_default='false'),
        # Session settings
        sa.Column('session_timeout_days', sa.Integer(), nullable=False, server_default='1'),
        # Auto-create admin (only for admin domain)
        sa.Column('auto_create_admin_on_first_sso', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('auto_create_admin_email_domains', postgresql.ARRAY(sa.String(255)), nullable=True),  # Allowed email domains for auto-create
        # Members-specific settings
        sa.Column('self_signup_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('signup_auto_create_personal_space', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('allowed_email_domains', postgresql.ARRAY(sa.String(255)), nullable=True),  # Restrict signup to these domains
        # Timestamps
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain', 'scope_type', 'scope_id', name='uq_auth_policies_domain_scope'),
    )
    op.create_index('ix_auth_policies_domain', 'auth_policies', ['domain'])
    op.create_index('ix_auth_policies_scope_type', 'auth_policies', ['scope_type'])
    op.create_index('ix_auth_policies_scope_id', 'auth_policies', ['scope_id'])

    # ==========================================
    # 4. user_profiles - Extended user profile data
    # ==========================================
    op.create_table(
        'user_profiles',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('avatar_object_key', sa.String(500), nullable=True),  # MinIO object key
        sa.Column('locale', sa.String(10), nullable=True, server_default='zh-CN'),
        sa.Column('timezone', sa.String(50), nullable=True, server_default='Asia/Shanghai'),
        sa.Column('preferences', postgresql.JSONB(), nullable=True),  # User preferences JSON
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # ==========================================
    # 5. branding_settings - Platform branding configuration
    # ==========================================
    op.create_table(
        'branding_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_type', postgresql.ENUM('system', 'tenant', 'user', name='settings_scope_type', create_type=False), nullable=False, server_default='system'),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('brand_name', sa.String(100), nullable=True),
        sa.Column('logo_object_key', sa.String(500), nullable=True),  # MinIO object key for logo
        sa.Column('favicon_object_key', sa.String(500), nullable=True),  # MinIO object key for favicon
        sa.Column('login_page_title', sa.String(200), nullable=True),
        sa.Column('dashboard_title', sa.String(200), nullable=True),
        sa.Column('browser_title_template', sa.String(200), nullable=True),  # e.g., "{page_title} - {brand_name}"
        sa.Column('login_background_object_key', sa.String(500), nullable=True),
        sa.Column('primary_color', sa.String(20), nullable=True),  # Hex color
        sa.Column('color_scheme_locked', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('custom_css', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope_type', 'scope_id', name='uq_branding_settings_scope'),
    )
    op.create_index('ix_branding_settings_scope_type', 'branding_settings', ['scope_type'])
    op.create_index('ix_branding_settings_scope_id', 'branding_settings', ['scope_id'])

    # ==========================================
    # 6. notification_channels - Notification channel configurations
    # ==========================================
    op.create_table(
        'notification_channels',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_type', postgresql.ENUM('system', 'tenant', 'user', name='settings_scope_type', create_type=False), nullable=False, server_default='system'),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('channel_type', postgresql.ENUM('smtp', 'webhook', 'slack', 'feishu', 'wecom', 'dingtalk', name='notification_channel_type', create_type=False), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        # Non-sensitive config (host, port, from_email, webhook_url patterns, etc.)
        sa.Column('config_json', postgresql.JSONB(), nullable=True),
        # Encrypted secrets (password, tokens, signing secrets)
        sa.Column('secrets_enc', sa.LargeBinary(), nullable=True),
        sa.Column('last_test_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_test_success', sa.Boolean(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope_type', 'scope_id', 'channel_type', 'name', name='uq_notification_channels_scope_type_name'),
    )
    op.create_index('ix_notification_channels_scope_type', 'notification_channels', ['scope_type'])
    op.create_index('ix_notification_channels_scope_id', 'notification_channels', ['scope_id'])
    op.create_index('ix_notification_channels_channel_type', 'notification_channels', ['channel_type'])
    op.create_index('ix_notification_channels_enabled', 'notification_channels', ['enabled'])

    # ==========================================
    # 7. notification_subscriptions - User/system event subscriptions
    # ==========================================
    op.create_table(
        'notification_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_type', postgresql.ENUM('system', 'tenant', 'user', name='settings_scope_type', create_type=False), nullable=False),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),  # e.g., 'node.offline', 'deployment.failed'
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('digest_enabled', sa.Boolean(), nullable=False, server_default='false'),  # Aggregate notifications
        sa.Column('digest_interval_minutes', sa.Integer(), nullable=True),
        sa.Column('filters', postgresql.JSONB(), nullable=True),  # Additional filters (e.g., specific nodes, severity)
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['channel_id'], ['notification_channels.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('scope_type', 'scope_id', 'channel_id', 'event_type', name='uq_notification_subscriptions'),
    )
    op.create_index('ix_notification_subscriptions_scope', 'notification_subscriptions', ['scope_type', 'scope_id'])
    op.create_index('ix_notification_subscriptions_channel_id', 'notification_subscriptions', ['channel_id'])
    op.create_index('ix_notification_subscriptions_event_type', 'notification_subscriptions', ['event_type'])

    # ==========================================
    # 8. security_policies - Security and compliance settings
    # ==========================================
    op.create_table(
        'security_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_type', postgresql.ENUM('system', 'tenant', 'user', name='settings_scope_type', create_type=False), nullable=False, server_default='system'),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),
        # Session policies
        sa.Column('session_idle_timeout_minutes', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('session_absolute_timeout_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('max_concurrent_sessions', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('force_logout_on_password_change', sa.Boolean(), nullable=False, server_default='true'),
        # Password policies
        sa.Column('password_min_length', sa.Integer(), nullable=False, server_default='8'),
        sa.Column('password_require_uppercase', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('password_require_lowercase', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('password_require_digit', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('password_require_special', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('password_history_count', sa.Integer(), nullable=False, server_default='5'),  # Cannot reuse last N passwords
        sa.Column('password_expiry_days', sa.Integer(), nullable=True),  # NULL = never expires
        # Login security
        sa.Column('max_login_attempts', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('lockout_duration_minutes', sa.Integer(), nullable=False, server_default='15'),
        # IP access control
        sa.Column('ip_allowlist', postgresql.ARRAY(sa.String(50)), nullable=True),  # CIDR notation
        sa.Column('ip_denylist', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('ip_access_control_enabled', sa.Boolean(), nullable=False, server_default='false'),
        # Audit logging
        sa.Column('audit_log_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('audit_log_retention_days', sa.Integer(), nullable=False, server_default='90'),
        # Egress control (for offline/air-gapped deployments)
        sa.Column('egress_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('egress_allowed_domains', postgresql.ARRAY(sa.String(255)), nullable=True),
        # Timestamps
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope_type', 'scope_id', name='uq_security_policies_scope'),
    )
    op.create_index('ix_security_policies_scope_type', 'security_policies', ['scope_type'])
    op.create_index('ix_security_policies_scope_id', 'security_policies', ['scope_id'])

    # ==========================================
    # 9. settings_audit_logs - Audit trail for settings changes
    # ==========================================
    op.create_table(
        'settings_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_type', postgresql.ENUM('system', 'tenant', 'user', name='settings_scope_type', create_type=False), nullable=False),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_email', sa.String(255), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),  # create, update, delete
        sa.Column('resource_type', sa.String(50), nullable=False),  # settings_kv, sso_provider, auth_policy, etc.
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('resource_key', sa.String(255), nullable=True),  # For settings_kv, the key
        sa.Column('old_value', postgresql.JSONB(), nullable=True),  # Previous value (sensitive fields redacted)
        sa.Column('new_value', postgresql.JSONB(), nullable=True),  # New value (sensitive fields redacted)
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_settings_audit_logs_scope', 'settings_audit_logs', ['scope_type', 'scope_id'])
    op.create_index('ix_settings_audit_logs_actor_id', 'settings_audit_logs', ['actor_id'])
    op.create_index('ix_settings_audit_logs_action', 'settings_audit_logs', ['action'])
    op.create_index('ix_settings_audit_logs_resource_type', 'settings_audit_logs', ['resource_type'])
    op.create_index('ix_settings_audit_logs_created_at', 'settings_audit_logs', ['created_at'])
    op.create_index('ix_settings_audit_logs_scope_created', 'settings_audit_logs', ['scope_type', 'scope_id', 'created_at'])

    # ==========================================
    # 10. sso_state_tokens - CSRF state for SSO flows
    # ==========================================
    op.create_table(
        'sso_state_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('state', sa.String(255), nullable=False, unique=True),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('nonce', sa.String(255), nullable=True),  # For OIDC
        sa.Column('code_verifier', sa.String(255), nullable=True),  # For PKCE
        sa.Column('redirect_uri', sa.String(500), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(), nullable=True),  # Any additional data needed after callback
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['provider_id'], ['sso_providers.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_sso_state_tokens_state', 'sso_state_tokens', ['state'])
    op.create_index('ix_sso_state_tokens_provider_id', 'sso_state_tokens', ['provider_id'])
    op.create_index('ix_sso_state_tokens_expires_at', 'sso_state_tokens', ['expires_at'])

    # ==========================================
    # 11. feature_flags - Feature toggles for the platform
    # ==========================================
    op.create_table(
        'feature_flags',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_type', postgresql.ENUM('system', 'tenant', 'user', name='settings_scope_type', create_type=False), nullable=False, server_default='system'),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('flag_key', sa.String(100), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope_type', 'scope_id', 'flag_key', name='uq_feature_flags_scope_key'),
    )
    op.create_index('ix_feature_flags_scope', 'feature_flags', ['scope_type', 'scope_id'])
    op.create_index('ix_feature_flags_flag_key', 'feature_flags', ['flag_key'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('feature_flags')
    op.drop_table('sso_state_tokens')
    op.drop_table('settings_audit_logs')
    op.drop_table('security_policies')
    op.drop_table('notification_subscriptions')
    op.drop_table('notification_channels')
    op.drop_table('branding_settings')
    op.drop_table('user_profiles')
    op.drop_table('auth_policies')
    op.drop_table('sso_providers')
    op.drop_table('settings_kv')

    # Drop enum types
    notification_channel_type_enum = postgresql.ENUM('smtp', 'webhook', 'slack', 'feishu', 'wecom', 'dingtalk', name='notification_channel_type')
    notification_channel_type_enum.drop(op.get_bind(), checkfirst=True)

    sso_provider_type_enum = postgresql.ENUM('saml', 'oidc', 'oauth2', name='sso_provider_type')
    sso_provider_type_enum.drop(op.get_bind(), checkfirst=True)

    auth_domain_enum = postgresql.ENUM('admin', 'members', 'webapp', name='auth_domain_type')
    auth_domain_enum.drop(op.get_bind(), checkfirst=True)

    scope_type_enum = postgresql.ENUM('system', 'tenant', 'user', name='settings_scope_type')
    scope_type_enum.drop(op.get_bind(), checkfirst=True)
