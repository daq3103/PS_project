"""Add limited-attempt email recovery codes, preserving existing reset links."""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("password_reset_tokens", sa.Column("code_hash", sa.String(64)))
    op.add_column("password_reset_tokens", sa.Column(
        "attempts", sa.Integer(), nullable=False, server_default="0"
    ))


def downgrade() -> None:
    op.drop_column("password_reset_tokens", "attempts")
    op.drop_column("password_reset_tokens", "code_hash")
