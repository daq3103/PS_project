"""Adoption workflow, idempotency and durable notifications.

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        "ALTER TABLE community_posts ADD COLUMN adoption_meta JSONB NOT NULL DEFAULT '{}'",
        "ALTER TABLE community_job_outbox ADD COLUMN locked_until TIMESTAMPTZ",
        "ALTER TABLE community_job_outbox ADD COLUMN last_error VARCHAR(100)",
        """CREATE TABLE adoption_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            post_id UUID NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            applicant_name VARCHAR(150) NOT NULL,
            applicant_phone VARCHAR(20) NOT NULL,
            applicant_address TEXT NOT NULL,
            living_condition TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','contacted','approved','completed','rejected','withdrawn')),
            admin_note VARCHAR(1000), outcome_reason VARCHAR(500),
            handled_by UUID REFERENCES users(id) ON DELETE SET NULL,
            completed_at TIMESTAMPTZ, anonymized_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        "CREATE UNIQUE INDEX uq_adoption_selected ON adoption_requests(post_id) WHERE status IN ('approved','completed')",
        "CREATE UNIQUE INDEX uq_adoption_active_user ON adoption_requests(post_id,user_id) WHERE status IN ('pending','contacted','approved','completed')",
        "CREATE INDEX idx_adoption_user ON adoption_requests(user_id,created_at DESC)",
        "CREATE INDEX idx_adoption_queue ON adoption_requests(status,created_at)",
        "ALTER TABLE community_audit_logs ADD COLUMN request_id UUID REFERENCES adoption_requests(id) ON DELETE SET NULL",
        "CREATE INDEX idx_community_audit_post ON community_audit_logs(post_id,created_at DESC)",
        """CREATE TABLE community_receipts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            operation VARCHAR(30) NOT NULL, key VARCHAR(100) NOT NULL,
            payload_hash VARCHAR(64) NOT NULL, resource_id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id,operation,key)
        )""",
        """CREATE TABLE community_notifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            unique_key VARCHAR(64) UNIQUE NOT NULL, message VARCHAR(300) NOT NULL,
            href VARCHAR(300) NOT NULL, read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        "CREATE INDEX idx_community_notifications_user ON community_notifications(user_id,created_at DESC)",
        "CREATE INDEX idx_community_outbox_due ON community_job_outbox(status,scheduled_at)",
        # Existing duplicate reports are kept as dismissed history before adding the constraint.
        """WITH ranked AS (SELECT id, row_number() OVER (
            PARTITION BY post_id,reporter_user_id ORDER BY created_at,id) AS n
            FROM community_reports WHERE status='pending')
            UPDATE community_reports SET status='dismissed',handled_at=NOW()
            WHERE id IN (SELECT id FROM ranked WHERE n>1)""",
        "CREATE UNIQUE INDEX uq_community_pending_report ON community_reports(post_id,reporter_user_id) WHERE status='pending'",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    for statement in [
        "DROP INDEX uq_community_pending_report", "DROP INDEX idx_community_outbox_due",
        "DROP TABLE community_notifications", "DROP TABLE community_receipts",
        "ALTER TABLE community_audit_logs DROP COLUMN request_id", "DROP INDEX idx_community_audit_post",
        "DROP TABLE adoption_requests", "ALTER TABLE community_job_outbox DROP COLUMN locked_until",
        "ALTER TABLE community_job_outbox DROP COLUMN last_error", "ALTER TABLE community_posts DROP COLUMN adoption_meta",
    ]:
        op.execute(statement)
