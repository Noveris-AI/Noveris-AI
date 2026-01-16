"""Add node management tables

Revision ID: 8a3c5f7e2d1b
Revises: fe28b8e0d255
Create Date: 2026-01-15 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8a3c5f7e2d1b'
down_revision = 'fe28b8e0d255'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types - use DO block to check if type exists before creating
    # This handles partial migration recovery gracefully
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE node_status AS ENUM ('NEW', 'READY', 'UNREACHABLE', 'MAINTENANCE', 'DECOMMISSIONED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE connection_type AS ENUM ('ssh', 'local', 'winrm');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_status AS ENUM ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED', 'TIMEOUT');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE auth_type AS ENUM ('ssh_key', 'password', 'api_key');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE bmc_protocol AS ENUM ('redfish', 'ipmi', 'none');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE accelerator_type AS ENUM ('nvidia_gpu', 'amd_gpu', 'intel_gpu', 'ascend_npu', 't_head_npu', 'generic_accel');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE node_type AS ENUM ('management', 'compute', 'login', 'storage', 'kube_node', 'kube_master', 'slurm_node', 'slurm_ctrl', 'edge', 'generic');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create node_groups table
    op.create_table(
        'node_groups',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255)),
        sa.Column('description', sa.Text),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('node_groups.id')),
        sa.Column('priority', sa.Integer, default=0),
        sa.Column('is_system', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_node_groups_tenant_id', 'node_groups', ['tenant_id'])
    op.create_unique_constraint('uq_node_group_tenant_name', 'node_groups', ['tenant_id', 'name'])

    # Create nodes table
    op.create_table(
        'nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255)),
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer, default=22),
        sa.Column('connection_type', postgresql.ENUM('ssh', 'local', 'winrm', name='connection_type', create_type=False), server_default='ssh', nullable=False),
        sa.Column('ssh_user', sa.String(100)),
        sa.Column('status', postgresql.ENUM('NEW', 'READY', 'UNREACHABLE', 'MAINTENANCE', 'DECOMMISSIONED', name='node_status', create_type=False), server_default='NEW', nullable=False),
        sa.Column('node_type', postgresql.ENUM('management', 'compute', 'login', 'storage', 'kube_node', 'kube_master', 'slurm_node', 'slurm_ctrl', 'edge', 'generic', name='node_type', create_type=False), server_default='generic'),
        sa.Column('labels', postgresql.JSONB, default=dict),
        sa.Column('tags', postgresql.ARRAY(sa.String), default=list),
        sa.Column('os_release', sa.String(100)),
        sa.Column('kernel_version', sa.String(100)),
        sa.Column('cpu_cores', sa.Integer),
        sa.Column('cpu_model', sa.String(255)),
        sa.Column('mem_mb', sa.Integer),
        sa.Column('disk_mb', sa.Integer),
        sa.Column('architecture', sa.String(50)),
        sa.Column('last_seen_at', sa.DateTime(timezone=True)),
        sa.Column('last_job_run_at', sa.DateTime(timezone=True)),
        sa.Column('last_job_id', postgresql.UUID(as_uuid=True)),
        sa.Column('connectivity_errors', postgresql.JSONB, default=list),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('decommissioned_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_nodes_tenant_id', 'nodes', ['tenant_id'])
    op.create_index('ix_nodes_status', 'nodes', ['status'])
    op.create_index('ix_nodes_host', 'nodes', ['host'])
    op.create_index('ix_nodes_last_seen', 'nodes', ['last_seen_at'])

    # Create node_group_association table
    op.create_table(
        'node_group_association',
        sa.Column('node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('node_group_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('node_groups.id', ondelete='CASCADE'), primary_key=True),
    )

    # Create node_credentials table
    op.create_table(
        'node_credentials',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('auth_type', postgresql.ENUM('ssh_key', 'password', 'api_key', name='auth_type', create_type=False), nullable=False),
        sa.Column('encrypted_payload', sa.Text, nullable=False),
        sa.Column('key_version', sa.Integer, default=1),
        sa.Column('bastion_host', sa.String(255)),
        sa.Column('bastion_port', sa.Integer, default=22),
        sa.Column('bastion_user', sa.String(100)),
        sa.Column('encrypted_bastion_auth', sa.Text),
        sa.Column('bastion_key_version', sa.Integer),
        sa.Column('last_rotated_at', sa.DateTime(timezone=True)),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_node_credentials_tenant_id', 'node_credentials', ['tenant_id'])

    # Create node_bmc_credentials table
    op.create_table(
        'node_bmc_credentials',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('bmc_host', sa.String(255), nullable=False),
        sa.Column('bmc_port', sa.Integer, default=443),
        sa.Column('bmc_protocol', postgresql.ENUM('redfish', 'ipmi', 'none', name='bmc_protocol', create_type=False), server_default='redfish'),
        sa.Column('bmc_user', sa.String(100), nullable=False),
        sa.Column('encrypted_password', sa.Text, nullable=False),
        sa.Column('key_version', sa.Integer, default=1),
        sa.Column('last_verified_at', sa.DateTime(timezone=True)),
        sa.Column('is_valid', sa.Boolean, default=None),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_node_bmc_credentials_tenant_id', 'node_bmc_credentials', ['tenant_id'])

    # Create group_vars table
    op.create_table(
        'group_vars',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('group_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('node_groups.id', ondelete='CASCADE'), nullable=True),
        sa.Column('vars', postgresql.JSONB, nullable=False, default=dict),
        sa.Column('version', sa.Integer, default=1),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True)),
        sa.Column('change_description', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_group_vars_tenant_id', 'group_vars', ['tenant_id'])
    op.create_index('ix_group_vars_scope', 'group_vars', ['scope'])
    op.create_index('ix_group_vars_group_id', 'group_vars', ['group_id'])

    # Create node_fact_snapshots table
    op.create_table(
        'node_fact_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('facts', postgresql.JSONB, nullable=False, default=dict),
        sa.Column('os_family', sa.String(50)),
        sa.Column('os_distribution', sa.String(100)),
        sa.Column('os_version', sa.String(50)),
        sa.Column('kernel_version', sa.String(100)),
        sa.Column('architecture', sa.String(50)),
        sa.Column('cpu_model', sa.String(255)),
        sa.Column('cpu_cores', sa.Integer),
        sa.Column('cpu_threads_per_core', sa.Integer),
        sa.Column('cpu_physical_cores', sa.Integer),
        sa.Column('mem_total_mb', sa.Integer),
        sa.Column('swap_total_mb', sa.Integer),
        sa.Column('network_interfaces', postgresql.JSONB),
        sa.Column('default_ipv4', sa.String(50)),
        sa.Column('default_ipv6', sa.String(50)),
        sa.Column('disks', postgresql.JSONB),
        sa.Column('disk_total_mb', sa.Integer),
        sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('collection_method', sa.String(50), default='ansible'),
        sa.Column('ansible_version', sa.String(50)),
    )
    op.create_index('ix_node_fact_snapshots_node_id', 'node_fact_snapshots', ['node_id'])
    op.create_index('ix_node_fact_snapshots_collected_at', 'node_fact_snapshots', ['collected_at'])

    # Create accelerators table
    op.create_table(
        'accelerators',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', postgresql.ENUM('nvidia_gpu', 'amd_gpu', 'intel_gpu', 'ascend_npu', 't_head_npu', 'generic_accel', name='accelerator_type', create_type=False), nullable=False),
        sa.Column('vendor', sa.String(100)),
        sa.Column('model', sa.String(255)),
        sa.Column('device_id', sa.String(100)),
        sa.Column('slot', sa.Integer),
        sa.Column('bus_id', sa.String(50)),
        sa.Column('numa_node', sa.Integer),
        sa.Column('topology', postgresql.JSONB, default=dict),
        sa.Column('count', sa.Integer, default=1),
        sa.Column('memory_mb', sa.Integer),
        sa.Column('cores', sa.Integer),
        sa.Column('mig_capable', sa.Boolean, default=False),
        sa.Column('mig_mode', postgresql.JSONB),
        sa.Column('compute_capability', sa.String(20)),
        sa.Column('driver_version', sa.String(100)),
        sa.Column('firmware_version', sa.String(100)),
        sa.Column('toolkit_version', sa.String(100)),
        sa.Column('health_status', sa.String(50), default='unknown'),
        sa.Column('temperature_celsius', sa.Integer),
        sa.Column('power_usage_watts', sa.Integer),
        sa.Column('utilization_percent', sa.Integer),
        sa.Column('pci_vendor_id', sa.String(10)),
        sa.Column('pci_device_id', sa.String(10)),
        sa.Column('subsystem_vendor_id', sa.String(10)),
        sa.Column('subsystem_device_id', sa.String(10)),
        sa.Column('discovered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_accelerators_node_id', 'accelerators', ['node_id'])
    op.create_index('ix_accelerators_type', 'accelerators', ['type'])

    # Create job_templates table
    op.create_table(
        'job_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('category', sa.String(100)),
        sa.Column('playbook_path', sa.String(500), nullable=False),
        sa.Column('roles_path', sa.String(500)),
        sa.Column('collections', postgresql.JSONB),
        sa.Column('target_type', sa.String(20), nullable=False),
        sa.Column('become', sa.Boolean, default=True),
        sa.Column('become_method', sa.String(20), default='sudo'),
        sa.Column('become_user', sa.String(50), default='root'),
        sa.Column('timeout_seconds', sa.Integer, default=3600),
        sa.Column('max_retries', sa.Integer, default=0),
        sa.Column('retry_delay_seconds', sa.Integer, default=60),
        sa.Column('supports_serial', sa.Boolean, default=False),
        sa.Column('default_serial', sa.String(50)),
        sa.Column('input_schema', postgresql.JSONB),
        sa.Column('input_ui_schema', postgresql.JSONB),
        sa.Column('default_vars', postgresql.JSONB, default=dict),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('is_system', sa.Boolean, default=False),
        sa.Column('required_roles', postgresql.ARRAY(sa.String), default=list),
        sa.Column('tags', postgresql.ARRAY(sa.String), default=list),
        sa.Column('version', sa.String(50)),
        sa.Column('author', sa.String(255)),
        sa.Column('documentation_url', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_job_templates_tenant_id', 'job_templates', ['tenant_id'])
    op.create_index('ix_job_templates_category', 'job_templates', ['category'])
    op.create_index('ix_job_templates_enabled', 'job_templates', ['enabled'])
    op.create_unique_constraint('uq_job_template_tenant_name', 'job_templates', ['tenant_id', 'name'])

    # Create job_runs table
    op.create_table(
        'job_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('job_templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('template_snapshot', postgresql.JSONB),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by_email', sa.String(255)),
        sa.Column('target_type', sa.String(20), nullable=False),
        sa.Column('target_node_ids', postgresql.JSONB),
        sa.Column('target_group_ids', postgresql.JSONB),
        sa.Column('extra_vars', postgresql.JSONB, default=dict),
        sa.Column('runtime_vars', postgresql.JSONB, default=dict),
        sa.Column('inventory_content', sa.Text),
        sa.Column('status', postgresql.ENUM('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED', 'TIMEOUT', name='job_status', create_type=False), server_default='PENDING', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('duration_seconds', sa.Integer),
        sa.Column('summary', postgresql.JSONB, default=dict),
        sa.Column('error_message', sa.Text),
        sa.Column('error_detail', sa.Text),
        sa.Column('artifacts_bucket', sa.String(255)),
        sa.Column('artifacts_prefix', sa.String(500)),
        sa.Column('canceled_at', sa.DateTime(timezone=True)),
        sa.Column('canceled_by', postgresql.UUID(as_uuid=True)),
        sa.Column('cancellation_reason', sa.Text),
        sa.Column('serial', sa.String(50)),
        sa.Column('current_batch', sa.Integer, default=0),
        sa.Column('total_batches', sa.Integer, default=1),
        sa.Column('worker_id', sa.String(255)),
        sa.Column('worker_pid', sa.Integer),
    )
    op.create_index('ix_job_runs_tenant_id', 'job_runs', ['tenant_id'])
    op.create_index('ix_job_runs_template_id', 'job_runs', ['template_id'])
    op.create_index('ix_job_runs_status', 'job_runs', ['status'])
    op.create_index('ix_job_runs_created_by', 'job_runs', ['created_by'])
    op.create_index('ix_job_runs_started_at', 'job_runs', ['started_at'])

    # Create job_run_nodes association table
    op.create_table(
        'job_run_nodes',
        sa.Column('job_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('job_runs.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='CASCADE'), primary_key=True),
    )

    # Create job_run_events table
    op.create_table(
        'job_run_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('job_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('job_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('seq', sa.Integer, nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('hostname', sa.String(255)),
        sa.Column('category', sa.String(50)),
        sa.Column('is_ok', sa.Boolean),
    )
    op.create_index('ix_job_run_events_job_run_id', 'job_run_events', ['job_run_id'])
    op.create_index('ix_job_run_events_ts', 'job_run_events', ['ts'])
    op.create_index('ix_job_run_events_event_type', 'job_run_events', ['event_type'])

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_email', sa.String(255)),
        sa.Column('actor_type', sa.String(50), default='user'),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True)),
        sa.Column('resource_name', sa.String(255)),
        sa.Column('diff', postgresql.JSONB),
        sa.Column('request_summary', postgresql.JSONB),
        sa.Column('status', sa.String(50), default='success'),
        sa.Column('error_message', sa.Text),
        sa.Column('ip_address', sa.String(50)),
        sa.Column('user_agent', sa.String(500)),
        sa.Column('session_id', sa.String(255)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('ix_audit_logs_actor_id', 'audit_logs', ['actor_id'])
    op.create_index('ix_audit_logs_resource_type', 'audit_logs', ['resource_type'])
    op.create_index('ix_audit_logs_resource_id', 'audit_logs', ['resource_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('audit_logs')
    op.drop_table('job_run_events')
    op.drop_table('job_run_nodes')
    op.drop_table('job_runs')
    op.drop_table('job_templates')
    op.drop_table('accelerators')
    op.drop_table('node_fact_snapshots')
    op.drop_table('group_vars')
    op.drop_table('node_bmc_credentials')
    op.drop_table('node_credentials')
    op.drop_table('node_group_association')
    op.drop_table('nodes')
    op.drop_table('node_groups')

    # Drop enum types - each separately for asyncpg compatibility
    op.execute("DROP TYPE IF EXISTS node_status")
    op.execute("DROP TYPE IF EXISTS connection_type")
    op.execute("DROP TYPE IF EXISTS job_status")
    op.execute("DROP TYPE IF EXISTS auth_type")
    op.execute("DROP TYPE IF EXISTS bmc_protocol")
    op.execute("DROP TYPE IF EXISTS accelerator_type")
    op.execute("DROP TYPE IF EXISTS node_type")
