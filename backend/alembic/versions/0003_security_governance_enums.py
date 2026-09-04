"""security governance enums

Revision ID: 0003_security_governance_enums
Revises: 0002_platform_capabilities
Create Date: 2026-07-17 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003_security_governance_enums"
down_revision: Union[str, None] = "0002_platform_capabilities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'CONSULTANT'")
    op.execute("ALTER TYPE case_priority ADD VALUE IF NOT EXISTS 'CRITICAL'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be safely removed without recreating the type.
    pass
