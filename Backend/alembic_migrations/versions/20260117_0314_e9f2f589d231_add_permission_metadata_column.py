"""add_permission_metadata_column

Revision ID: e9f2f589d231
Revises: 20260118_0002
Create Date: 2026-01-17 03:14:07.980208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9f2f589d231'
down_revision: Union[str, None] = '20260118_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database."""
    # Add permission_metadata column to authz_permissions table
    op.add_column(
        'authz_permissions',
        sa.Column('permission_metadata', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade database."""
    # Remove permission_metadata column from authz_permissions table
    op.drop_column('authz_permissions', 'permission_metadata')
