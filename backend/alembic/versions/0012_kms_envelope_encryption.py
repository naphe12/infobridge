"""support AWS KMS envelope encryption

Revision ID: 0012_kms_envelope_encryption
Revises: 0011_attachment_purge_tracking
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_kms_envelope_encryption"
down_revision: Union[str, None] = "0011_attachment_purge_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("attachments", "encryption_key_ref", type_=sa.String(length=512), existing_type=sa.String(length=120))
    op.add_column(
        "attachments",
        sa.Column("encryption_algorithm", sa.String(length=40), nullable=False, server_default="FERNET"),
    )
    op.add_column("attachments", sa.Column("encrypted_data_key", sa.Text(), nullable=True))
    op.add_column("attachments", sa.Column("encryption_nonce", sa.String(length=64), nullable=True))
    op.alter_column("attachments", "encryption_algorithm", server_default=None)


def downgrade() -> None:
    op.drop_column("attachments", "encryption_nonce")
    op.drop_column("attachments", "encrypted_data_key")
    op.drop_column("attachments", "encryption_algorithm")
    op.alter_column("attachments", "encryption_key_ref", type_=sa.String(length=120), existing_type=sa.String(length=512))
