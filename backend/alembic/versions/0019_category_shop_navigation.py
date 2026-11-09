"""Choose which active categories appear in the Shop navigation."""
import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("categories", sa.Column("show_in_nav", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE categories SET show_in_nav = true WHERE slug IN ('thuc-an-hat', 'phu-kien')")


def downgrade():
    op.drop_column("categories", "show_in_nav")
