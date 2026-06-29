"""platform capabilities

Revision ID: 0002_platform_capabilities
Revises: 0001_initial_schema
Create Date: 2026-06-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_platform_capabilities"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for value in ("AUDITOR",):
        op.execute(f"ALTER TYPE user_role ADD VALUE IF NOT EXISTS '{value}'")

    for value in ("ASSIGNED", "IN_PROGRESS", "PENDING_VALIDATION", "RESPONSE_SENT"):
        op.execute(f"ALTER TYPE case_status ADD VALUE IF NOT EXISTS '{value}'")

    op.add_column("exchange_cases", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("exchange_cases", sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("exchange_cases", sa.Column("validated_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("exchange_cases", sa.Column("response_body", sa.Text(), nullable=True))
    op.add_column("exchange_cases", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exchange_cases", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exchange_cases", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exchange_cases", sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exchange_cases", sa.Column("response_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exchange_cases", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exchange_cases", sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_exchange_cases_assigned_to_users", "exchange_cases", "users", ["assigned_to"], ["id"])
    op.create_foreign_key("fk_exchange_cases_validated_by_users", "exchange_cases", "users", ["validated_by"], ["id"])
    op.create_index("ix_exchange_cases_assigned_to", "exchange_cases", ["assigned_to"])

    op.add_column("attachments", sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("attachments", sa.Column("purpose", sa.String(length=80), nullable=False, server_default="REQUEST"))
    op.add_column("attachments", sa.Column("encrypted", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("attachments", sa.Column("encryption_key_ref", sa.String(length=120), nullable=True))
    op.alter_column("attachments", "message_id", nullable=True)
    op.create_foreign_key("fk_attachments_case_id_exchange_cases", "attachments", "exchange_cases", ["case_id"], ["id"])
    op.create_index("ix_attachments_case_id", "attachments", ["case_id"])
    op.alter_column("attachments", "purpose", server_default=None)
    op.alter_column("attachments", "encrypted", server_default=None)

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id"), nullable=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exchange_cases.id"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("level", sa.String(length=40), nullable=False, server_default="INFO"),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_institution_id", "notifications", ["institution_id"])
    op.create_index("ix_notifications_case_id", "notifications", ["case_id"])

    op.create_table(
        "api_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("client_key", sa.String(length=120), nullable=False),
        sa.Column("secret_hash", sa.String(length=255), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_clients_client_key", "api_clients", ["client_key"], unique=True)


def downgrade() -> None:
    op.drop_table("api_clients")
    op.drop_table("notifications")
    op.drop_index("ix_attachments_case_id", table_name="attachments")
    op.drop_constraint("fk_attachments_case_id_exchange_cases", "attachments", type_="foreignkey")
    op.drop_column("attachments", "encryption_key_ref")
    op.drop_column("attachments", "encrypted")
    op.drop_column("attachments", "purpose")
    op.drop_column("attachments", "case_id")
    op.alter_column("attachments", "message_id", nullable=False)

    op.drop_index("ix_exchange_cases_assigned_to", table_name="exchange_cases")
    op.drop_constraint("fk_exchange_cases_validated_by_users", "exchange_cases", type_="foreignkey")
    op.drop_constraint("fk_exchange_cases_assigned_to_users", "exchange_cases", type_="foreignkey")
    for column_name in (
        "retention_until",
        "closed_at",
        "response_sent_at",
        "validated_at",
        "received_at",
        "sent_at",
        "due_at",
        "response_body",
        "validated_by",
        "assigned_to",
        "description",
    ):
        op.drop_column("exchange_cases", column_name)
