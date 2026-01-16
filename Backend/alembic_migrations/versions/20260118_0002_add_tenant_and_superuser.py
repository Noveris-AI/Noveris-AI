"""Add tenant_id and is_superuser to users table

Revision ID: 20260118_0002
Revises: 20260118_0001
Create Date: 2026-01-18 00:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260118_0002"
down_revision: Union[str, None] = "20260118_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tenant_id and is_superuser columns to users table."""

    # Use bind to check if columns exist
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]

    # Add tenant_id column if it doesn't exist
    if 'tenant_id' not in columns:
        op.add_column(
            "users",
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
                comment="Tenant ID for multi-tenancy support",
            ),
        )
        # Add index for tenant_id
        op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # Add is_superuser column if it doesn't exist
    if 'is_superuser' not in columns:
        op.add_column(
            "users",
            sa.Column(
                "is_superuser",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
                comment="Super admin with full system access",
            ),
        )
        # Add index for is_superuser
        op.create_index("ix_users_is_superuser", "users", ["is_superuser"])


def downgrade() -> None:
    """Remove tenant_id and is_superuser columns from users table."""

    # Use bind to check if columns and indexes exist
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]
    indexes = [idx['name'] for idx in inspector.get_indexes('users')]

    # Drop indexes first (if they exist)
    if "ix_users_is_superuser" in indexes:
        op.drop_index("ix_users_is_superuser", table_name="users")
    if "ix_users_tenant_id" in indexes:
        op.drop_index("ix_users_tenant_id", table_name="users")

    # Drop columns (if they exist)
    if "is_superuser" in columns:
        op.drop_column("users", "is_superuser")
    if "tenant_id" in columns:
        op.drop_column("users", "tenant_id")
