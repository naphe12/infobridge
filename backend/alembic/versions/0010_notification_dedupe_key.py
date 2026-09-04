"""deduplicate scheduled notifications

Revision ID: 0010_notification_dedupe_key
Revises: 0009_attachment_storage_backend
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_notification_dedupe_key"
down_revision: Union[str, None] = "0009_attachment_storage_backend"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("dedupe_key", sa.String(length=255), nullable=True))
    op.create_index("ix_notifications_dedupe_key", "notifications", ["dedupe_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_notifications_dedupe_key", table_name="notifications")
    op.drop_column("notifications", "dedupe_key")
