"""Add shelter registry, care, reporting and internal fund bookkeeping. No role grants."""

from pathlib import Path

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    sql = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8-sig")
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    op.drop_table("rescue_publications")
    op.drop_table("rescue_supply_receipts")
    for table in [
        "rescue_expenses",
        "rescue_ledger",
        "rescue_funds",
        "rescue_audit",
        "rescue_operation_receipts",
        "rescue_reports",
        "rescue_tasks",
        "rescue_events",
        "rescue_episodes",
        "rescue_cases",
        "rescue_locations",
        "rescue_animals",
    ]:
        op.drop_table(table)
