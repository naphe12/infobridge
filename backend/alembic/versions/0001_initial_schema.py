"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    institution_type = postgresql.ENUM("MINISTRY", "BANK", "COMMUNE", "AGENCY", "OPERATOR", "PRIVATE", "OTHER", name="institution_type")
    institution_status = postgresql.ENUM("ACTIVE", "SUSPENDED", "ARCHIVED", name="institution_status")
    user_role = postgresql.ENUM("SYSTEM_ADMIN", "INSTITUTION_ADMIN", "AGENT", "VALIDATOR", "OBSERVER", name="user_role")
    user_status = postgresql.ENUM("ACTIVE", "LOCKED", "DISABLED", name="user_status")
    case_status = postgresql.ENUM("DRAFT", "SENT", "RECEIVED", "IN_REVIEW", "APPROVED", "REJECTED", "CLOSED", "ARCHIVED", name="case_status")
    case_priority = postgresql.ENUM("LOW", "NORMAL", "HIGH", "URGENT", name="case_priority")
    classification = postgresql.ENUM("PUBLIC", "INTERNE", "CONFIDENTIEL", "SECRET", name="classification")
    workflow_status = postgresql.ENUM("PENDING", "IN_PROGRESS", "APPROVED", "REJECTED", "CLOSED", name="workflow_status")
    security_severity = postgresql.ENUM("LOW", "MEDIUM", "HIGH", "CRITICAL", name="security_severity")

    institution_type.create(op.get_bind())
    institution_status.create(op.get_bind())
    user_role.create(op.get_bind())
    user_status.create(op.get_bind())
    case_status.create(op.get_bind())
    case_priority.create(op.get_bind())
    classification.create(op.get_bind())
    workflow_status.create(op.get_bind())
    security_severity.create(op.get_bind())

    op.create_table(
        "institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("type", institution_type, nullable=False),
        sa.Column("status", institution_status, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_institutions_code", "institutions", ["code"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("status", user_status, nullable=False, server_default="ACTIVE"),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_institution_id", "users", ["institution_id"])

    op.create_table(
        "exchange_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference", sa.String(length=80), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("sender_institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("receiver_institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("status", case_status, nullable=False, server_default="DRAFT"),
        sa.Column("priority", case_priority, nullable=False, server_default="NORMAL"),
        sa.Column("classification", classification, nullable=False, server_default="INTERNE"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_exchange_cases_reference", "exchange_cases", ["reference"], unique=True)
    op.create_index("ix_exchange_cases_sender", "exchange_cases", ["sender_institution_id"])
    op.create_index("ix_exchange_cases_receiver", "exchange_cases", ["receiver_institution_id"])
    op.create_index("ix_exchange_cases_status", "exchange_cases", ["status"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exchange_cases.id"), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_messages_case_id", "messages", ["case_id"])

    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("mime_type", sa.String(length=150), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_attachments_message_id", "attachments", ["message_id"])
    op.create_index("ix_attachments_checksum", "attachments", ["checksum"])

    op.create_table(
        "receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exchange_cases.id"), nullable=False),
        sa.Column("receiver_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_receipts_case_id", "receipts", ["case_id"])

    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exchange_cases.id"), nullable=False),
        sa.Column("current_step", sa.String(length=100), nullable=False),
        sa.Column("status", workflow_status, nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflows_case_id", "workflows", ["case_id"])

    op.create_table(
        "workflow_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_actions_workflow_id", "workflow_actions", ["workflow_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id"), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id"), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("severity", security_severity, nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_security_events_type", "security_events", ["event_type"])
    op.create_index("ix_security_events_created_at", "security_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("security_events")
    op.drop_table("audit_logs")
    op.drop_table("workflow_actions")
    op.drop_table("workflows")
    op.drop_table("receipts")
    op.drop_table("attachments")
    op.drop_table("messages")
    op.drop_table("exchange_cases")
    op.drop_table("users")
    op.drop_table("institutions")

    for enum_name in (
        "security_severity",
        "workflow_status",
        "classification",
        "case_priority",
        "case_status",
        "user_status",
        "user_role",
        "institution_status",
        "institution_type",
    ):
        postgresql.ENUM(name=enum_name).drop(op.get_bind())
