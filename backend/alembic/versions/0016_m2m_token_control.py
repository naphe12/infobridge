"""strengthen M2M client token control

Revision ID: 0016_m2m_token_control
Revises: 0015_reference_data
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_m2m_token_control"
down_revision: Union[str, None] = "0015_reference_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("api_clients", sa.Column("token_version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("api_clients", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("api_clients", sa.Column("secret_rotated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE api_clients SET scopes = CASE "
        "WHEN scopes ~ '(^| )cases:read( |$)' THEN 'cases:read' "
        "ELSE '' END"
    )


def downgrade() -> None:
    op.drop_column("api_clients", "secret_rotated_at")
    op.drop_column("api_clients", "updated_at")
    op.drop_column("api_clients", "token_version")
