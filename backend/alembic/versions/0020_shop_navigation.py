"""Store the Shop navigation order and custom internal links."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "shop_navigation_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("items", JSONB(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_shop_navigation_singleton"),
    )


def downgrade():
    op.drop_table("shop_navigation_settings")
