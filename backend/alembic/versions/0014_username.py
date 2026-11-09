"""Username credentials and verified recovery email."""
import sqlalchemy as sa
from alembic import op
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("password_reset_tokens", sa.Column("target_email", sa.String(255)))
    op.add_column("users", sa.Column("username", sa.String(40), unique=True))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"))

def downgrade():
    op.drop_column("password_reset_tokens", "target_email")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "username")
