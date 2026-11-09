"""Explicit, one-use approval for linking a verified Google Gmail identity."""
import sqlalchemy as sa
from alembic import op
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("google_email_link_allowed", sa.Boolean(), nullable=False, server_default="false"))

def downgrade():
    op.drop_column("users", "google_email_link_allowed")
