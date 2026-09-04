"""document versioning metadata
Revision ID: 0008_attachment_versions
Revises: 0007_receipts_unique
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
revision: str = "0008_attachment_versions"
down_revision: Union[str, None] = "0007_receipts_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    op.add_column("attachments", sa.Column("logical_document_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("attachments", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("attachments", sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE attachments SET logical_document_id = id WHERE logical_document_id IS NULL")
    op.alter_column("attachments", "logical_document_id", nullable=False)
    op.create_foreign_key("fk_attachments_supersedes", "attachments", "attachments", ["supersedes_id"], ["id"])
    op.create_index("ix_attachments_logical_document_id", "attachments", ["logical_document_id"])
    op.create_unique_constraint("uq_attachment_document_version", "attachments", ["logical_document_id", "version"])
    op.alter_column("attachments", "version", server_default=None)
def downgrade() -> None:
    op.drop_constraint("uq_attachment_document_version", "attachments", type_="unique")
    op.drop_index("ix_attachments_logical_document_id", table_name="attachments")
    op.drop_constraint("fk_attachments_supersedes", "attachments", type_="foreignkey")
    op.drop_column("attachments", "supersedes_id")
    op.drop_column("attachments", "version")
    op.drop_column("attachments", "logical_document_id")
