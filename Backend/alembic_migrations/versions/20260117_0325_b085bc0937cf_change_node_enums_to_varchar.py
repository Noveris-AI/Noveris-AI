"""change_node_enums_to_varchar

Revision ID: b085bc0937cf
Revises: 3af42673ab15
Create Date: 2026-01-17 03:25:43.727017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b085bc0937cf'
down_revision: Union[str, None] = '3af42673ab15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database."""
    # Convert enum columns to VARCHAR in nodes table
    op.execute("ALTER TABLE nodes ALTER COLUMN connection_type TYPE VARCHAR(20) USING connection_type::text")
    op.execute("ALTER TABLE nodes ALTER COLUMN status TYPE VARCHAR(20) USING status::text")
    op.execute("ALTER TABLE nodes ALTER COLUMN node_type TYPE VARCHAR(20) USING node_type::text")

    # Convert enum columns in node_credentials table
    op.execute("ALTER TABLE node_credentials ALTER COLUMN auth_type TYPE VARCHAR(20) USING auth_type::text")

    # Convert enum columns in node_bmc_credentials table
    op.execute("ALTER TABLE node_bmc_credentials ALTER COLUMN bmc_protocol TYPE VARCHAR(20) USING bmc_protocol::text")

    # Convert enum columns in accelerators table
    op.execute("ALTER TABLE accelerators ALTER COLUMN type TYPE VARCHAR(30) USING type::text")

    # Convert enum columns in job_runs table
    op.execute("ALTER TABLE job_runs ALTER COLUMN status TYPE VARCHAR(20) USING status::text")


def downgrade() -> None:
    """Downgrade database."""
    # Convert back to enum types (note: this requires the enum types to exist)
    op.execute("ALTER TABLE nodes ALTER COLUMN connection_type TYPE connection_type USING connection_type::connection_type")
    op.execute("ALTER TABLE nodes ALTER COLUMN status TYPE node_status USING status::node_status")
    op.execute("ALTER TABLE nodes ALTER COLUMN node_type TYPE node_type USING node_type::node_type")
    op.execute("ALTER TABLE node_credentials ALTER COLUMN auth_type TYPE auth_type USING auth_type::auth_type")
    op.execute("ALTER TABLE node_bmc_credentials ALTER COLUMN bmc_protocol TYPE bmc_protocol USING bmc_protocol::bmc_protocol")
    op.execute("ALTER TABLE accelerators ALTER COLUMN type TYPE accelerator_type USING type::accelerator_type")
    op.execute("ALTER TABLE job_runs ALTER COLUMN status TYPE job_status USING status::job_status")
