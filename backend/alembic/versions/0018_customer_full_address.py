"""Allow one-line customer address entry while retaining legacy address parts."""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customer_addresses", sa.Column("full_address", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("customer_addresses", "full_address")
