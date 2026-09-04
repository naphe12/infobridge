"""track attachment storage backend
Revision ID: 0009_attachment_storage_backend
Revises: 0008_attachment_versions
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
revision: str = "0009_attachment_storage_backend"
down_revision: Union[str, None] = "0008_attachment_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    op.add_column("attachments", sa.Column("storage_backend", sa.String(20), nullable=False, server_default="local"))
    op.alter_column("attachments", "storage_backend", server_default=None)
def downgrade() -> None:
    op.drop_column("attachments", "storage_backend")
