"""Bind checkout retries to their owner and original request."""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("orders", sa.Column("guest_token_hash", sa.String(64), nullable=True))
    op.add_column("orders", sa.Column("request_hash", sa.String(64), nullable=True))

def downgrade():
    op.drop_column("orders", "request_hash")
    op.drop_column("orders", "guest_token_hash")
