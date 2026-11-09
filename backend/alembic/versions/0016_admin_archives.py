"""Archive administrative records without deleting business history."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op
revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("admin_archives",
        sa.Column("resource_kind", sa.String(20), primary_key=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    op.drop_table("admin_archives")
