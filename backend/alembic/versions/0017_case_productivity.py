"""Case checklists, discussions, approval circuits and temporary delegations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = "0017_case_productivity"
down_revision = "0016_m2m_token_control"
branch_labels = None
depends_on = None


def base_columns():
    return [sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)]


def fk(name, table):
    return sa.Column(name, UUID(as_uuid=True), sa.ForeignKey(f"{table}.id"), nullable=False)


def upgrade():
    op.add_column("exchange_cases", sa.Column("request_type", sa.String(80), nullable=False, server_default="GENERAL"))
    op.add_column("exchange_cases", sa.Column("validation_steps", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("exchange_cases", sa.Column("validation_progress", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table("case_policies", *base_columns(), fk("institution_id", "institutions"),
                    sa.Column("name", sa.String(150), nullable=False), sa.Column("request_type", sa.String(80), nullable=False),
                    sa.Column("classification", sa.String(30)), sa.Column("required_purposes", sa.JSON(), nullable=False),
                    sa.Column("validation_roles", sa.JSON(), nullable=False), sa.Column("active", sa.Boolean(), nullable=False))
    op.create_table("case_comments", *base_columns(), fk("case_id", "exchange_cases"), fk("institution_id", "institutions"),
                    fk("author_id", "users"), sa.Column("visibility", sa.String(20), nullable=False),
                    sa.Column("body", sa.Text(), nullable=False), sa.Column("mentions", sa.JSON(), nullable=False))
    op.create_table("case_delegations", *base_columns(), fk("case_id", "exchange_cases"), fk("owner_id", "users"),
                    fk("delegate_id", "users"), fk("created_by", "users"),
                    sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)))
    for table, columns in {"case_policies": ["institution_id"], "case_comments": ["case_id", "institution_id"],
                           "case_delegations": ["case_id", "delegate_id"]}.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in ("case_delegations", "case_comments", "case_policies"):
        op.drop_table(table)
    for column in ("validation_progress", "validation_steps", "request_type"):
        op.drop_column("exchange_cases", column)
