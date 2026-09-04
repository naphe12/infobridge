"""track physical attachment purges

Revision ID: 0011_attachment_purge_tracking
Revises: 0010_notification_dedupe_key
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_attachment_purge_tracking"
down_revision: Union[str, None] = "0010_notification_dedupe_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("attachments", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("attachments", sa.Column("purge_error", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("attachments", "purge_error")
    op.drop_column("attachments", "purged_at")
