"""oauth_states: allow sign-in attempts that have no user yet

The backend now owns Google sign-in as well as connector consent, so the same
single-use state table serves both. A connector attempt is started by a
signed-in user and stays bound to them. A sign-in attempt has no user yet —
establishing who the user is *is* the point of the round trip — so user_id
becomes nullable and a purpose column keeps the two kinds apart.

purpose matters for safety, not bookkeeping: a state minted for sign-in must
not be redeemable at the connector callback, or an attacker could start a
sign-in and land the resulting grant on someone else's account. Each callback
checks the purpose it expects.

Revision ID: f3c9a2e15b48
Revises: e2b5d81c4f70
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3c9a2e15b48"
down_revision: Union[str, None] = "e2b5d81c4f70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONNECT = "connect"
SIGNIN = "signin"


def upgrade() -> None:
    # In-flight authorisation attempts are seconds old and single-use; the
    # shape is changing under them, so drop rather than migrate them.
    op.execute("DELETE FROM oauth_states")

    with op.batch_alter_table("oauth_states") as batch:
        batch.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch.add_column(
            sa.Column(
                "purpose",
                sa.String(length=16),
                nullable=False,
                server_default=CONNECT,
            )
        )

    op.create_index(
        "ix_oauth_states_purpose",
        "oauth_states",
        ["purpose"],
    )


def downgrade() -> None:
    # Rows with no user cannot exist once user_id is NOT NULL again.
    op.execute("DELETE FROM oauth_states")

    op.drop_index("ix_oauth_states_purpose", table_name="oauth_states")

    with op.batch_alter_table("oauth_states") as batch:
        batch.drop_column("purpose")
        batch.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
