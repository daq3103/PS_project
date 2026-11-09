"""Durable checkout jobs, quotes, support and payment exceptions. Additive only."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def uid(name="id", **kw):
    return sa.Column(name, pg.UUID(as_uuid=True), **kw)


def upgrade():
    op.add_column(
        "order_items",
        sa.Column("discount_amount", sa.BigInteger(), nullable=False, server_default="0"),
    )
    # Historical order totals remain unchanged. Allocate their recorded discount deterministically.
    op.execute("""
        WITH shares AS (
            SELECT oi.id, oi.line_total, o.discount_amount, o.subtotal_amount,
                   SUM(oi.line_total) OVER (PARTITION BY oi.order_id ORDER BY oi.id) AS cumulative
            FROM order_items oi JOIN orders o ON o.id = oi.order_id
        ), allocated AS (
            SELECT id, CASE WHEN subtotal_amount > 0 THEN
                floor(discount_amount::numeric * cumulative / subtotal_amount)::bigint -
                floor(discount_amount::numeric * (cumulative - line_total) / subtotal_amount)::bigint
                ELSE 0 END AS amount FROM shares
        ) UPDATE order_items oi SET discount_amount = allocated.amount FROM allocated WHERE oi.id = allocated.id
    """)
    op.create_table(
        "commerce_jobs",
        uid(primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("business_key", sa.String(180), nullable=False, unique=True),
        sa.Column("task", sa.String(80), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        uid("lease_token"),
        sa.Column("last_error", sa.String(100)),
        sa.Column("result", pg.JSONB()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_commerce_jobs_due", "commerce_jobs", ["status", "next_attempt_at"])
    op.create_table(
        "operation_cases",
        uid(primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("business_key", sa.String(200), nullable=False, unique=True),
        uid("order_id", nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text()),
        uid("resolved_by"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.Column("resolution_reference", sa.String(150), unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "checkout_quotes",
        uid(primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_key", sa.String(80), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("totals", pg.JSONB(), nullable=False),
        sa.Column("lines", pg.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        uid("order_id"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
    )
    op.create_index("ix_checkout_quotes_expiry", "checkout_quotes", ["expires_at"])
    op.create_table(
        "support_tickets",
        uid(primary_key=True, server_default=sa.text("gen_random_uuid()")),
        uid("user_id", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        uid("order_id"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.Column("subject", sa.String(150), nullable=False),
        sa.Column("topic", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_support_tickets_owner", "support_tickets", ["user_id", "created_at"])
    op.create_index("ix_support_tickets_queue", "support_tickets", ["status", "created_at"])
    op.create_table(
        "support_messages",
        uid(primary_key=True, server_default=sa.text("gen_random_uuid()")),
        uid("ticket_id", nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"]),
        uid("user_id", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.Column("author_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_support_messages_ticket", "support_messages", ["ticket_id", "created_at"])


def downgrade():
    for table in [
        "support_messages",
        "support_tickets",
        "checkout_quotes",
        "operation_cases",
        "commerce_jobs",
    ]:
        op.drop_table(table)
    op.drop_column("order_items", "discount_amount")
