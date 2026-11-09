"""Keep owner verification on the authenticated session, not each operation."""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("refresh_tokens", sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column("refresh_tokens", "mfa_verified")
