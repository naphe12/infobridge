"""enforce append-only audit log

Revision ID: 0013_audit_log_append_only
Revises: 0012_kms_envelope_encryption
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013_audit_log_append_only"
down_revision: Union[str, None] = "0012_kms_envelope_encryption"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_audit_log_row_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only: % is forbidden', TG_OP
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_immutable_rows
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_row_mutation()
        """
    )
    op.execute("ALTER TABLE audit_logs ENABLE ALWAYS TRIGGER audit_logs_immutable_rows")
    op.execute(
        """
        CREATE FUNCTION prevent_audit_log_truncate()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only: TRUNCATE is forbidden'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_immutable_truncate
        BEFORE TRUNCATE ON audit_logs
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_audit_log_truncate()
        """
    )
    op.execute("ALTER TABLE audit_logs ENABLE ALWAYS TRIGGER audit_logs_immutable_truncate")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable_truncate ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_truncate()")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable_rows ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_row_mutation()")
