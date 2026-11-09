"""Keep an audit trail for staff role changes."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("staff_permissions", ARRAY(sa.String(30)), nullable=False, server_default="{}"),
    )
    op.execute("UPDATE users SET staff_permissions = ARRAY['warehouse'] WHERE role = 'warehouse_staff'")
    op.execute("UPDATE users SET staff_permissions = ARRAY['customer_support'] WHERE role = 'cskh_staff'")
    op.create_table(
        "staff_role_changes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("old_role", sa.String(20), nullable=False),
        sa.Column("new_role", sa.String(20), nullable=False),
        sa.Column("old_permissions", ARRAY(sa.String(30)), nullable=False),
        sa.Column("new_permissions", ARRAY(sa.String(30)), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_staff_role_changes_target_user_id", "staff_role_changes", ["target_user_id"])


def downgrade() -> None:
    op.drop_index("ix_staff_role_changes_target_user_id", table_name="staff_role_changes")
    op.drop_table("staff_role_changes")
    op.drop_column("users", "staff_permissions")
