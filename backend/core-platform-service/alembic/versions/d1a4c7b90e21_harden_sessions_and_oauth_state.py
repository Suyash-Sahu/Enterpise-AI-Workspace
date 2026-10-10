"""harden sessions and oauth state

Adds refresh-token rotation, revocation and reuse-detection columns to
`sessions`, and binds `oauth_states` to a user with a TTL.

Existing rows cannot be migrated: `sessions` stored raw refresh tokens with no
family or jti, and `oauth_states` has no user to attribute rows to. Both tables
hold only short-lived transient state, so they are cleared. The practical
effect is that everyone is signed out once, and any in-flight Google
authorisation must be restarted.

Revision ID: d1a4c7b90e21
Revises: 8f9a7f5d8cc7
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1a4c7b90e21"
down_revision: Union[str, Sequence[str], None] = "8f9a7f5d8cc7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table so this also applies on SQLite, which cannot drop or
    # re-constrain a column with a plain ALTER.

    # --- sessions ----------------------------------------------------------
    op.execute("DELETE FROM sessions")

    with op.batch_alter_table("sessions") as batch:
        batch.add_column(
            sa.Column("token_hash", sa.String(length=64), nullable=False)
        )
        batch.add_column(sa.Column("jti", sa.String(length=64), nullable=False))
        batch.add_column(
            sa.Column("family_id", sa.String(length=64), nullable=False)
        )
        batch.add_column(
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("revoked_reason", sa.String(length=64), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch.drop_column("refresh_token")
        batch.create_unique_constraint("uq_sessions_token_hash", ["token_hash"])
        batch.create_unique_constraint("uq_sessions_jti", ["jti"])

    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"])
    op.create_index("ix_sessions_jti", "sessions", ["jti"])
    op.create_index("ix_sessions_family_id", "sessions", ["family_id"])
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index(
        "ix_sessions_user_active", "sessions", ["user_id", "is_active"]
    )

    # --- oauth_states ------------------------------------------------------
    op.execute("DELETE FROM oauth_states")

    with op.batch_alter_table("oauth_states") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=False))
        batch.add_column(
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False)
        )
        batch.create_foreign_key(
            "fk_oauth_states_user_id",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.create_index("ix_oauth_states_user_id", "oauth_states", ["user_id"])
    op.create_index("ix_oauth_states_state", "oauth_states", ["state"])


def downgrade() -> None:
    op.execute("DELETE FROM oauth_states")
    op.drop_index("ix_oauth_states_state", table_name="oauth_states")
    op.drop_index("ix_oauth_states_user_id", table_name="oauth_states")
    op.drop_constraint(
        "fk_oauth_states_user_id", "oauth_states", type_="foreignkey"
    )
    op.drop_column("oauth_states", "expires_at")
    op.drop_column("oauth_states", "user_id")

    op.execute("DELETE FROM sessions")
    op.drop_index("ix_sessions_user_active", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_index("ix_sessions_family_id", table_name="sessions")
    op.drop_index("ix_sessions_jti", table_name="sessions")
    op.drop_index("ix_sessions_token_hash", table_name="sessions")
    op.drop_constraint("uq_sessions_jti", "sessions", type_="unique")
    op.drop_constraint("uq_sessions_token_hash", "sessions", type_="unique")

    op.add_column(
        "sessions",
        sa.Column("refresh_token", sa.String(length=500), nullable=False),
    )
    op.drop_column("sessions", "is_active")
    op.drop_column("sessions", "revoked_reason")
    op.drop_column("sessions", "revoked_at")
    op.drop_column("sessions", "consumed_at")
    op.drop_column("sessions", "family_id")
    op.drop_column("sessions", "jti")
    op.drop_column("sessions", "token_hash")
