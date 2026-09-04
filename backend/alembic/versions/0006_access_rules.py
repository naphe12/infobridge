"""configurable access rules
Revision ID: 0006_access_rules
Revises: 0005_api_client_institution
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
revision: str = "0006_access_rules"
down_revision: Union[str, None] = "0005_api_client_institution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    op.create_table("access_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id"), nullable=True),
        sa.Column("role", postgresql.ENUM(name="user_role", create_type=False), nullable=False),
        sa.Column("permission", sa.String(80), nullable=False), sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_classification", postgresql.ENUM(name="classification", create_type=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("institution_id", "role", "permission", name="uq_access_rule_scope"))
    op.create_index("ix_access_rules_institution_id", "access_rules", ["institution_id"])
def downgrade() -> None:
    op.drop_table("access_rules")
