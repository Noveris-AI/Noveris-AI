"""Add model deployment tables

Revision ID: 9b4d6f8e3c2a
Revises: 8a3c5f7e2d1b
Create Date: 2026-01-15 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9b4d6f8e3c2a'
down_revision = '8a3c5f7e2d1b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types using DO blocks to handle partial migration recovery
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deployment_framework AS ENUM ('vllm', 'sglang', 'xinference');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deployment_status AS ENUM ('PENDING', 'DOWNLOADING', 'INSTALLING', 'STARTING', 'RUNNING', 'STOPPED', 'FAILED', 'DELETING');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deployment_mode AS ENUM ('native', 'docker');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE model_source AS ENUM ('huggingface', 'modelscope', 'local');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create secrets_kv table
    op.create_table(
        'secrets_kv',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(500), nullable=False),
        sa.Column('ciphertext', sa.Text, nullable=False),
        sa.Column('key_version', sa.Integer, default=1),
        sa.Column('description', sa.String(500)),
        sa.Column('created_by', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_secrets_kv_tenant_id', 'secrets_kv', ['tenant_id'])
    op.create_unique_constraint('uq_secrets_kv_tenant_key', 'secrets_kv', ['tenant_id', 'key'])

    # Create deployments table
    op.create_table(
        'deployments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255)),
        sa.Column('description', sa.Text),
        sa.Column('framework', postgresql.ENUM('vllm', 'sglang', 'xinference', name='deployment_framework', create_type=False), nullable=False),
        sa.Column('deployment_mode', postgresql.ENUM('native', 'docker', name='deployment_mode', create_type=False), default='native'),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('model_source', postgresql.ENUM('huggingface', 'modelscope', 'local', name='model_source', create_type=False), default='huggingface'),
        sa.Column('model_repo_id', sa.String(500), nullable=False),
        sa.Column('model_revision', sa.String(100)),
        sa.Column('model_local_path', sa.String(1000)),
        sa.Column('host', sa.String(255), default='0.0.0.0'),
        sa.Column('port', sa.Integer, nullable=False),
        sa.Column('served_model_name', sa.String(255)),
        sa.Column('gpu_devices', postgresql.ARRAY(sa.Integer)),
        sa.Column('tensor_parallel_size', sa.Integer, default=1),
        sa.Column('gpu_memory_utilization', sa.Float, default=0.9),
        sa.Column('env_table', postgresql.JSONB, default=list),
        sa.Column('args_table', postgresql.JSONB, default=list),
        sa.Column('sensitive_env_refs', postgresql.JSONB, default=dict),
        sa.Column('status', postgresql.ENUM('PENDING', 'DOWNLOADING', 'INSTALLING', 'STARTING', 'RUNNING', 'STOPPED', 'FAILED', 'DELETING', name='deployment_status', create_type=False), default='PENDING', nullable=False),
        sa.Column('health_status', sa.String(50), default='unknown'),
        sa.Column('last_health_check_at', sa.DateTime(timezone=True)),
        sa.Column('health_check_error', sa.Text),
        sa.Column('endpoints', postgresql.JSONB, default=dict),
        sa.Column('systemd_service_name', sa.String(255)),
        sa.Column('systemd_unit_path', sa.String(500)),
        sa.Column('wrapper_script_path', sa.String(500)),
        sa.Column('config_json_path', sa.String(500)),
        sa.Column('pid_file_path', sa.String(500)),
        sa.Column('log_dir', sa.String(500)),
        sa.Column('stdout_log_path', sa.String(500)),
        sa.Column('stderr_log_path', sa.String(500)),
        sa.Column('install_job_run_id', postgresql.UUID(as_uuid=True)),
        sa.Column('start_job_run_id', postgresql.UUID(as_uuid=True)),
        sa.Column('stop_job_run_id', postgresql.UUID(as_uuid=True)),
        sa.Column('uninstall_job_run_id', postgresql.UUID(as_uuid=True)),
        sa.Column('error_message', sa.Text),
        sa.Column('error_detail', sa.Text),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('max_retries', sa.Integer, default=3),
        sa.Column('labels', postgresql.JSONB, default=dict),
        sa.Column('tags', postgresql.ARRAY(sa.String), default=list),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by_email', sa.String(255)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('stopped_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_deployments_tenant_id', 'deployments', ['tenant_id'])
    op.create_index('ix_deployments_node_id', 'deployments', ['node_id'])
    op.create_index('ix_deployments_status', 'deployments', ['status'])
    op.create_index('ix_deployments_framework', 'deployments', ['framework'])
    op.create_unique_constraint('uq_deployment_tenant_name', 'deployments', ['tenant_id', 'name'])

    # Create deployment_logs table
    op.create_table(
        'deployment_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('deployment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('level', sa.String(20), default='info'),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('source', sa.String(100)),
        sa.Column('operation', sa.String(50)),
        sa.Column('job_run_id', postgresql.UUID(as_uuid=True)),
        sa.Column('data', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_deployment_logs_deployment_id', 'deployment_logs', ['deployment_id'])
    op.create_index('ix_deployment_logs_created_at', 'deployment_logs', ['created_at'])
    op.create_index('ix_deployment_logs_level', 'deployment_logs', ['level'])

    # Create port_allocations table
    op.create_table(
        'port_allocations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('port', sa.Integer, nullable=False),
        sa.Column('deployment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('deployments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('allocated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('released_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_port_allocations_tenant_id', 'port_allocations', ['tenant_id'])
    op.create_index('ix_port_allocations_node_id', 'port_allocations', ['node_id'])
    op.create_unique_constraint('uq_port_allocation_node_port', 'port_allocations', ['node_id', 'port'])

    # Create deployment_compatibility table
    op.create_table(
        'deployment_compatibility',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('framework', postgresql.ENUM('vllm', 'sglang', 'xinference', name='deployment_framework', create_type=False), nullable=False),
        sa.Column('supported', sa.Boolean, nullable=False),
        sa.Column('reason', sa.Text),
        sa.Column('install_profile', sa.String(50)),
        sa.Column('capabilities', postgresql.JSONB),
        sa.Column('requirements', postgresql.JSONB),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_deployment_compatibility_node_id', 'deployment_compatibility', ['node_id'])
    op.create_unique_constraint('uq_deployment_compatibility_node_framework', 'deployment_compatibility', ['node_id', 'framework'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('deployment_compatibility')
    op.drop_table('port_allocations')
    op.drop_table('deployment_logs')
    op.drop_table('deployments')
    op.drop_table('secrets_kv')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS deployment_framework")
    op.execute("DROP TYPE IF EXISTS deployment_status")
    op.execute("DROP TYPE IF EXISTS deployment_mode")
    op.execute("DROP TYPE IF EXISTS model_source")
