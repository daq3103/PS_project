"""Community rescue module schema.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE community_uploads (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        uploader_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        object_key VARCHAR(64) UNIQUE NOT NULL,
        original_filename VARCHAR(255),
        content_type VARCHAR(50) NOT NULL,
        size_bytes INT NOT NULL DEFAULT 0,
        width INT,
        height INT,
        status VARCHAR(20) NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'ready', 'rejected')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE community_posts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        author_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        post_type VARCHAR(20) NOT NULL
            CHECK (post_type IN ('lost_pet', 'found_pet', 'adoption')),
        title VARCHAR(255) NOT NULL,
        slug VARCHAR(300) UNIQUE NOT NULL,
        description TEXT,
        pet_type VARCHAR(20) NOT NULL,
        breed VARCHAR(100),
        color VARCHAR(100),
        location_detail VARCHAR(500),
        province_id INT NOT NULL,
        province_name VARCHAR(100) NOT NULL,
        district_id INT,
        district_name VARCHAR(100),
        ward_code VARCHAR(50),
        ward_name VARCHAR(100),
        last_seen_at TIMESTAMPTZ,
        found_at TIMESTAMPTZ,
        contact_phone VARCHAR(20) NOT NULL,
        contact_zalo VARCHAR(20),
        contact_facebook VARCHAR(255),
        moderation_status VARCHAR(20) NOT NULL DEFAULT 'pending'
            CHECK (moderation_status IN ('pending', 'approved', 'rejected', 'hidden')),
        lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'open'
            CHECK (lifecycle_status IN ('open', 'resolved', 'closed', 'expired')),
        resolved_at TIMESTAMPTZ,
        resolution_note VARCHAR(500),
        expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        moderated_by UUID REFERENCES users(id) ON DELETE SET NULL,
        moderated_at TIMESTAMPTZ,
        moderation_reason VARCHAR(500),
        version INT NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE community_post_images (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        post_id UUID NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
        upload_id UUID NOT NULL REFERENCES community_uploads(id) ON DELETE CASCADE,
        sort_order INT NOT NULL DEFAULT 0
    )
    """)

    op.execute("""
    CREATE TABLE community_reports (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        reporter_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        post_id UUID NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
        reason TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'resolved', 'dismissed')),
        handled_by UUID REFERENCES users(id) ON DELETE SET NULL,
        handled_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE community_audit_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        post_id UUID REFERENCES community_posts(id) ON DELETE CASCADE,
        action VARCHAR(50) NOT NULL,
        old_status VARCHAR(50),
        new_status VARCHAR(50),
        reason VARCHAR(500),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE community_job_outbox (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        job_type VARCHAR(50) NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}',
        status VARCHAR(20) NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'processing', 'done', 'failed')),
        attempt_count SMALLINT NOT NULL DEFAULT 0,
        unique_key VARCHAR(64) UNIQUE,
        scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        processed_at TIMESTAMPTZ
    )
    """)

    op.execute("""
    CREATE INDEX idx_community_posts_feed
        ON community_posts(post_type, moderation_status, lifecycle_status, expires_at)
    """)
    op.execute("""
    CREATE INDEX idx_community_posts_province_approved
        ON community_posts(province_id, moderation_status)
    """)
    op.execute("""
    CREATE INDEX idx_community_posts_created_cursor
        ON community_posts(created_at, id)
    """)
    op.execute("""
    CREATE INDEX idx_community_posts_author
        ON community_posts(author_user_id, created_at DESC)
    """)
    op.execute("""
    CREATE INDEX idx_community_uploads_uploader
        ON community_uploads(uploader_user_id, status)
    """)
    op.execute("""
    CREATE INDEX idx_community_reports_post
        ON community_reports(post_id, status)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS community_job_outbox")
    op.execute("DROP TABLE IF EXISTS community_audit_logs")
    op.execute("DROP TABLE IF EXISTS community_reports")
    op.execute("DROP TABLE IF EXISTS community_post_images")
    op.execute("DROP TABLE IF EXISTS community_posts")
    op.execute("DROP TABLE IF EXISTS community_uploads")
