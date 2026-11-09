"""Optional pet traits and searchable text; preserves existing rescue posts."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# Match Python NFD normalization for Vietnamese text, including historical posts.
ACCENTED = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
PLAIN = "a" * 17 + "e" * 11 + "i" * 5 + "o" * 17 + "u" * 11 + "y" * 5 + "d"


def upgrade() -> None:
    op.add_column(
        "community_posts",
        sa.Column("pet_details", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "community_posts", sa.Column("search_text", sa.Text(), nullable=False, server_default="")
    )
    op.execute(
        sa.text("""UPDATE community_posts SET search_text = translate(lower(
        concat_ws(' ', title, description, breed, color,
                  CASE pet_type WHEN 'cat' THEN 'mèo' WHEN 'dog' THEN 'chó' ELSE 'khác' END)),
                  :accented, :plain)""").bindparams(accented=ACCENTED, plain=PLAIN)
    )
    # Frozen aliases for existing free-text breed fields; original text is preserved.
    old_aliases = {
        "aln": "meo anh long ngan",
        "anh long ngan": "meo anh long ngan",
        "british shorthair": "meo anh long ngan",
        "ald": "meo anh long dai",
        "anh long dai": "meo anh long dai",
        "british longhair": "meo anh long dai",
        "persian": "meo ba tu",
        "siamese": "meo xiem",
        "meo nha": "meo ta",
        "pom": "cho phoc soc",
        "pomeranian": "cho phoc soc",
        "cho co": "cho ta",
        "shiba inu": "cho shiba",
        "alaskan malamute": "cho alaska",
        "german shepherd": "cho becgie",
        "bec gie": "cho becgie",
        "golden": "cho golden retriever",
    }
    for alias, expanded in old_aliases.items():
        op.execute(
            sa.text("""UPDATE community_posts SET search_text = search_text || ' ' || :expanded
            WHERE translate(lower(trim(breed)), :accented, :plain) = :alias""").bindparams(
                alias=alias, expanded=expanded, accented=ACCENTED, plain=PLAIN
            )
        )
    op.create_index(
        "ix_community_pet_details", "community_posts", ["pet_details"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_community_pet_details", table_name="community_posts")
    op.drop_column("community_posts", "search_text")
    op.drop_column("community_posts", "pet_details")
