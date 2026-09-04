"""enforce one receipt per case and user
Revision ID: 0007_receipts_unique
Revises: 0006_access_rules
"""
from typing import Sequence, Union
from alembic import op
revision: str = "0007_receipts_unique"
down_revision: Union[str, None] = "0006_access_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    op.execute("""DELETE FROM receipts WHERE id IN (
                    SELECT id FROM (
                      SELECT id, row_number() OVER (
                        PARTITION BY case_id, receiver_user_id ORDER BY received_at, id
                      ) AS duplicate_number FROM receipts
                    ) duplicates WHERE duplicate_number > 1
                  )""")
    op.create_unique_constraint("uq_receipt_case_user", "receipts", ["case_id", "receiver_user_id"])
def downgrade() -> None:
    op.drop_constraint("uq_receipt_case_user", "receipts", type_="unique")
