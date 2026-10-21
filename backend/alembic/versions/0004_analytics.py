"""First-party traffic and browser performance measurements.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE analytics_events (
        event_id UUID NOT NULL,
        kind VARCHAR(16) NOT NULL CHECK (kind IN ('page_view','LCP','INP','CLS','TTFB')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        visitor_hash VARCHAR(64) NOT NULL,
        session_hash VARCHAR(64) NOT NULL,
        page VARCHAR(80) NOT NULL,
        section VARCHAR(16) NOT NULL,
        source VARCHAR(16) NOT NULL,
        device VARCHAR(16) NOT NULL,
        value DOUBLE PRECISION CHECK (value >= 0),
        PRIMARY KEY (event_id, kind)
    )""")
    op.execute("CREATE INDEX ix_analytics_created_kind ON analytics_events (created_at, kind)")


def downgrade() -> None:
    op.drop_table("analytics_events")
