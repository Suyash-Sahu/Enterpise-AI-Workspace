"""constrain oauth_tokens

Adds the foreign key, index and one-active-grant-per-user constraint that
`oauth_tokens` never had. Duplicate active rows accumulated on every reconnect,
which is why every read sorted by id and took the newest.

Existing duplicates are collapsed before the unique index is created: for each
user the newest active grant is kept and older ones are deactivated. No grant
is deleted, so nothing has to be reconnected.

Revision ID: e2b5d81c4f70
Revises: d1a4c7b90e21
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b5d81c4f70"
down_revision: Union[str, Sequence[str], None] = "d1a4c7b90e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Deactivate every active grant that is not the newest for its user.
    conn.execute(
        sa.text(
            """
            UPDATE oauth_tokens
               SET is_active = :inactive
             WHERE is_active = :active
               AND id NOT IN (
                   SELECT MAX(id) FROM oauth_tokens
                    WHERE is_active = :active
                    GROUP BY user_id
               )
            """
        ),
        {"active": True, "inactive": False},
    )

    # 2. Drop rows whose user no longer exists, so the FK can be added.
    conn.execute(
        sa.text(
            """
            DELETE FROM oauth_tokens
             WHERE user_id NOT IN (SELECT id FROM users)
            """
        )
    )

    # 3. is_active must not be nullable for the partial index predicate.
    op.execute("UPDATE oauth_tokens SET is_active = FALSE WHERE is_active IS NULL")

    with op.batch_alter_table("oauth_tokens") as batch:
        batch.alter_column(
            "is_active",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        )
        batch.create_foreign_key(
            "fk_oauth_tokens_user_id",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # An earlier revision already created this on some databases.
    existing = {
        ix["name"] for ix in sa.inspect(conn).get_indexes("oauth_tokens")
    }
    if "ix_oauth_tokens_user_id" not in existing:
        op.create_index("ix_oauth_tokens_user_id", "oauth_tokens", ["user_id"])

    # 4. One active grant per user. Partial so deactivated rows stay as history.
    op.create_index(
        "uq_oauth_tokens_active_user",
        "oauth_tokens",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        sqlite_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("uq_oauth_tokens_active_user", table_name="oauth_tokens")

    with op.batch_alter_table("oauth_tokens") as batch:
        batch.drop_constraint("fk_oauth_tokens_user_id", type_="foreignkey")
        batch.alter_column(
            "is_active",
            existing_type=sa.Boolean(),
            nullable=True,
            server_default=None,
        )
