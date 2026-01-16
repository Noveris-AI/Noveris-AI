"""Add monitoring tables

Revision ID: 20260118_0001
Revises: 20260117_0001_settings
Create Date: 2026-01-18 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260118_0001'
down_revision: Union[str, None] = '20260117_0001_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types - using DO blocks to handle existing types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE targettype AS ENUM (
                'node', 'gateway', 'model', 'accelerator', 'blackbox', 'custom'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE adaptervendor AS ENUM (
                'nvidia', 'huawei_ascend', 'aliyun_npu', 'amd', 'intel', 'custom'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE adaptermode AS ENUM (
                'prometheus', 'cloud_api', 'exec'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE alertseverity AS ENUM (
                'info', 'warning', 'critical'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eventlevel AS ENUM (
                'debug', 'info', 'warning', 'error', 'critical'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eventtype AS ENUM (
                'node_up', 'node_down', 'node_reboot',
                'model_load', 'model_unload', 'model_error', 'model_cold_start',
                'route_change', 'upstream_change', 'circuit_breaker',
                'alert_firing', 'alert_resolved', 'alert_ack', 'alert_silence',
                'ssh_login_failed', 'ssh_login_success', 'unauthorized_access', 'file_integrity_violation',
                'config_change', 'budget_warning', 'budget_exceeded',
                'adapter_error', 'scrape_failure'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE budgetscope AS ENUM (
                'tenant', 'node', 'api_key', 'model'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE budgetwindow AS ENUM (
                'hourly', 'daily', 'weekly', 'monthly'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # monitoring_settings table
    op.create_table(
        'monitoring_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prometheus_url', sa.String(2000), server_default='http://localhost:9090'),
        sa.Column('prometheus_enabled', sa.Boolean(), server_default='true'),
        sa.Column('prometheus_auth_type', sa.String(50), server_default='none'),
        sa.Column('prometheus_auth_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('loki_url', sa.String(2000), server_default='http://localhost:3100'),
        sa.Column('loki_enabled', sa.Boolean(), server_default='true'),
        sa.Column('loki_auth_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('tempo_url', sa.String(2000), server_default='http://localhost:3200'),
        sa.Column('tempo_enabled', sa.Boolean(), server_default='false'),
        sa.Column('tempo_auth_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('alertmanager_url', sa.String(2000), server_default='http://localhost:9093'),
        sa.Column('alertmanager_enabled', sa.Boolean(), server_default='true'),
        sa.Column('alertmanager_auth_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('enabled_domains', postgresql.JSONB(astext_type=sa.Text()), server_default='{"nodes": true, "accelerators": true, "models": true, "gateway": true, "jobs": true, "network": true, "cost": true, "security": true}'),
        sa.Column('default_range', sa.String(20), server_default='1h'),
        sa.Column('max_range', sa.String(20), server_default='30d'),
        sa.Column('cache_ttl_seconds', sa.Integer(), server_default='30'),
        sa.Column('query_timeout_seconds', sa.Integer(), server_default='30'),
        sa.Column('default_mode', sa.String(20), server_default='simple'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id')
    )
    op.create_index('ix_monitoring_settings_tenant_id', 'monitoring_settings', ['tenant_id'])

    # monitoring_targets table
    op.create_table(
        'monitoring_targets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000)),
        sa.Column('type', postgresql.ENUM('node', 'gateway', 'model', 'accelerator', 'blackbox', 'custom', name='targettype', create_type=False), nullable=False),
        sa.Column('scrape_url', sa.String(2000), nullable=False),
        sa.Column('scrape_interval', sa.String(20), server_default='30s'),
        sa.Column('scrape_timeout', sa.String(20), server_default='10s'),
        sa.Column('metrics_path', sa.String(500), server_default='/metrics'),
        sa.Column('tls_enabled', sa.Boolean(), server_default='false'),
        sa.Column('tls_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('basic_auth_enabled', sa.Boolean(), server_default='false'),
        sa.Column('basic_auth_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('labels', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('related_entity_type', sa.String(50)),
        sa.Column('related_entity_id', postgresql.UUID(as_uuid=True)),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('last_scrape_at', sa.DateTime(timezone=True)),
        sa.Column('last_scrape_status', sa.String(50)),
        sa.Column('last_scrape_error', sa.Text()),
        sa.Column('scrape_sample_count', sa.Integer()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'scrape_url', name='uq_monitoring_targets_tenant_url')
    )
    op.create_index('ix_monitoring_targets_tenant_id', 'monitoring_targets', ['tenant_id'])
    op.create_index('ix_monitoring_targets_type', 'monitoring_targets', ['type'])
    op.create_index('ix_monitoring_targets_enabled', 'monitoring_targets', ['enabled'])

    # monitoring_adapters table
    op.create_table(
        'monitoring_adapters',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000)),
        sa.Column('vendor', postgresql.ENUM('nvidia', 'huawei_ascend', 'aliyun_npu', 'amd', 'intel', 'custom', name='adaptervendor', create_type=False), nullable=False),
        sa.Column('mode', postgresql.ENUM('prometheus', 'cloud_api', 'exec', name='adaptermode', create_type=False), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('mapping', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('label_mapping', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('extra_labels', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('last_collection_at', sa.DateTime(timezone=True)),
        sa.Column('last_collection_status', sa.String(50)),
        sa.Column('last_collection_error', sa.Text()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_monitoring_adapters_tenant_name')
    )
    op.create_index('ix_monitoring_adapters_tenant_id', 'monitoring_adapters', ['tenant_id'])
    op.create_index('ix_monitoring_adapters_vendor', 'monitoring_adapters', ['vendor'])
    op.create_index('ix_monitoring_adapters_enabled', 'monitoring_adapters', ['enabled'])

    # monitoring_dashboards table
    op.create_table(
        'monitoring_dashboards',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('title_i18n_key', sa.String(255), nullable=False),
        sa.Column('description_i18n_key', sa.String(255)),
        sa.Column('layout', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('simple_mode_metrics', postgresql.JSONB(astext_type=sa.Text()), server_default='[]'),
        sa.Column('advanced_mode_metrics', postgresql.JSONB(astext_type=sa.Text()), server_default='[]'),
        sa.Column('thresholds', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('help_tooltips', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'key', name='uq_monitoring_dashboards_tenant_key')
    )
    op.create_index('ix_monitoring_dashboards_tenant_id', 'monitoring_dashboards', ['tenant_id'])
    op.create_index('ix_monitoring_dashboards_key', 'monitoring_dashboards', ['key'])

    # monitoring_alert_rules table
    op.create_table(
        'monitoring_alert_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000)),
        sa.Column('group', sa.String(100), server_default='default'),
        sa.Column('expr', sa.Text(), nullable=False),
        sa.Column('for_duration', sa.String(20), server_default='5m'),
        sa.Column('severity', postgresql.ENUM('info', 'warning', 'critical', name='alertseverity', create_type=False), nullable=False, server_default='warning'),
        sa.Column('labels', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('annotations', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('routing', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('template_name', sa.String(100)),
        sa.Column('template_params', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_monitoring_alert_rules_tenant_name')
    )
    op.create_index('ix_monitoring_alert_rules_tenant_id', 'monitoring_alert_rules', ['tenant_id'])
    op.create_index('ix_monitoring_alert_rules_severity', 'monitoring_alert_rules', ['severity'])
    op.create_index('ix_monitoring_alert_rules_enabled', 'monitoring_alert_rules', ['enabled'])

    # monitoring_events table
    op.create_table(
        'monitoring_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', postgresql.ENUM(
            'node_up', 'node_down', 'node_reboot',
            'model_load', 'model_unload', 'model_error', 'model_cold_start',
            'route_change', 'upstream_change', 'circuit_breaker',
            'alert_firing', 'alert_resolved', 'alert_ack', 'alert_silence',
            'ssh_login_failed', 'ssh_login_success', 'unauthorized_access', 'file_integrity_violation',
            'config_change', 'budget_warning', 'budget_exceeded',
            'adapter_error', 'scrape_failure',
            name='eventtype', create_type=False
        ), nullable=False),
        sa.Column('level', postgresql.ENUM('debug', 'info', 'warning', 'error', 'critical', name='eventlevel', create_type=False), nullable=False, server_default='info'),
        sa.Column('node_id', postgresql.UUID(as_uuid=True)),
        sa.Column('model_id', postgresql.UUID(as_uuid=True)),
        sa.Column('deployment_id', postgresql.UUID(as_uuid=True)),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True)),
        sa.Column('alert_fingerprint', sa.String(100)),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('source', sa.String(100)),
        sa.Column('triggered_by', postgresql.UUID(as_uuid=True)),
        sa.Column('alert_acknowledged', sa.Boolean(), server_default='false'),
        sa.Column('alert_acknowledged_by', postgresql.UUID(as_uuid=True)),
        sa.Column('alert_acknowledged_at', sa.DateTime(timezone=True)),
        sa.Column('alert_acknowledged_note', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_monitoring_events_tenant_id', 'monitoring_events', ['tenant_id'])
    op.create_index('ix_monitoring_events_type', 'monitoring_events', ['type'])
    op.create_index('ix_monitoring_events_level', 'monitoring_events', ['level'])
    op.create_index('ix_monitoring_events_node_id', 'monitoring_events', ['node_id'])
    op.create_index('ix_monitoring_events_model_id', 'monitoring_events', ['model_id'])
    op.create_index('ix_monitoring_events_created_at', 'monitoring_events', ['created_at'])
    op.create_index('ix_monitoring_events_tenant_created', 'monitoring_events', ['tenant_id', 'created_at'])

    # monitoring_cost_profiles table
    op.create_table(
        'monitoring_cost_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000)),
        sa.Column('accelerator_prices', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('energy_cost', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('token_prices', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('default_currency', sa.String(10), server_default='USD'),
        sa.Column('is_default', sa.Boolean(), server_default='false'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_monitoring_cost_profiles_tenant_name')
    )
    op.create_index('ix_monitoring_cost_profiles_tenant_id', 'monitoring_cost_profiles', ['tenant_id'])

    # monitoring_budgets table
    op.create_table(
        'monitoring_budgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(1000)),
        sa.Column('scope', postgresql.ENUM('tenant', 'node', 'api_key', 'model', name='budgetscope', create_type=False), nullable=False),
        sa.Column('scope_target', sa.String(500)),
        sa.Column('limit_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('limit_currency', sa.String(10), server_default='USD'),
        sa.Column('window', postgresql.ENUM('hourly', 'daily', 'weekly', 'monthly', name='budgetwindow', create_type=False), nullable=False, server_default='monthly'),
        sa.Column('alert_thresholds', postgresql.JSONB(astext_type=sa.Text()), server_default='[50, 80, 100]'),
        sa.Column('notification_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('current_spending', sa.Numeric(precision=12, scale=2), server_default='0'),
        sa.Column('current_period_start', sa.DateTime(timezone=True)),
        sa.Column('last_updated_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(20), server_default='normal'),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_monitoring_budgets_tenant_id', 'monitoring_budgets', ['tenant_id'])
    op.create_index('ix_monitoring_budgets_scope', 'monitoring_budgets', ['scope'])
    op.create_index('ix_monitoring_budgets_enabled', 'monitoring_budgets', ['enabled'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('monitoring_budgets')
    op.drop_table('monitoring_cost_profiles')
    op.drop_table('monitoring_events')
    op.drop_table('monitoring_alert_rules')
    op.drop_table('monitoring_dashboards')
    op.drop_table('monitoring_adapters')
    op.drop_table('monitoring_targets')
    op.drop_table('monitoring_settings')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS budgetwindow')
    op.execute('DROP TYPE IF EXISTS budgetscope')
    op.execute('DROP TYPE IF EXISTS eventtype')
    op.execute('DROP TYPE IF EXISTS eventlevel')
    op.execute('DROP TYPE IF EXISTS alertseverity')
    op.execute('DROP TYPE IF EXISTS adaptermode')
    op.execute('DROP TYPE IF EXISTS adaptervendor')
    op.execute('DROP TYPE IF EXISTS targettype')
