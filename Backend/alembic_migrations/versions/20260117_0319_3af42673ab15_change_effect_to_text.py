"""change_effect_to_text

Revision ID: 3af42673ab15
Revises: e9f2f589d231
Create Date: 2026-01-17 03:19:29.271893

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3af42673ab15'
down_revision: Union[str, None] = 'e9f2f589d231'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database."""
    # Change effect column from enum to text in authz_role_permissions
    op.execute("ALTER TABLE authz_role_permissions ALTER COLUMN effect TYPE VARCHAR(10) USING effect::text")

    # Change effect column from enum to text in authz_user_permission_overrides
    op.execute("ALTER TABLE authz_user_permission_overrides ALTER COLUMN effect TYPE VARCHAR(10) USING effect::text")


def downgrade() -> None:
    """Downgrade database."""
    # Convert back to enum type
    op.execute("ALTER TABLE authz_role_permissions ALTER COLUMN effect TYPE permission_effect USING effect::permission_effect")
    op.execute("ALTER TABLE authz_user_permission_overrides ALTER COLUMN effect TYPE permission_effect USING effect::permission_effect")
