"""scope API clients to institutions

Revision ID: 0005_api_client_institution
Revises: 0004_auth_sessions
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_api_client_institution"
down_revision: Union[str, None] = "0004_auth_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("api_clients", sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_api_clients_institution", "api_clients", "institutions", ["institution_id"], ["id"])
    op.create_index("ix_api_clients_institution_id", "api_clients", ["institution_id"])

def downgrade() -> None:
    op.drop_index("ix_api_clients_institution_id", table_name="api_clients")
    op.drop_constraint("fk_api_clients_institution", "api_clients", type_="foreignkey")
    op.drop_column("api_clients", "institution_id")
