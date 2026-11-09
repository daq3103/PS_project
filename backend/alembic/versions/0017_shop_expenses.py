"""Record Shop expenses for seven-day earnings reports."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("shop_expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("reference", sa.String(150)),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("voided_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("void_reason", sa.Text()),
        sa.CheckConstraint("category IN ('shipping','supplies','other')", name="ck_shop_expense_category"),
        sa.CheckConstraint("amount > 0", name="ck_shop_expense_amount"),
    )
    op.create_index("ix_shop_expenses_spent_on", "shop_expenses", ["spent_on"])
    op.create_table("shop_expense_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("expense_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shop_expenses.id"), nullable=False),
        sa.Column("storage_key", sa.String(80), nullable=False, unique=True),
        sa.Column("uploader_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("shop_expense_receipts")
    op.drop_index("ix_shop_expenses_spent_on", table_name="shop_expenses")
    op.drop_table("shop_expenses")
