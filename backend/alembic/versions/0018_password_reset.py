"""One-use password recovery tokens and persistent request throttling."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = "0018_password_reset"
down_revision = "0017_case_productivity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("password_resets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])
    op.create_table("password_reset_throttles", sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_password_reset_throttles_expires_at", "password_reset_throttles", ["expires_at"])


def downgrade():
    op.drop_table("password_reset_throttles")
    op.drop_table("password_resets")
