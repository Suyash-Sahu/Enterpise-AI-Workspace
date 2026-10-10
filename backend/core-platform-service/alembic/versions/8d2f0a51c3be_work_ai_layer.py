"""AMOF Work stage 4: ai_proposals, work_autonomy_grants, work_ai_settings

Revision ID: 8d2f0a51c3be
Revises: 7c1e9d40b2aa
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "8d2f0a51c3be"
down_revision = "7c1e9d40b2aa"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "ai_proposals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, index=True),
        sa.Column("project_id", sa.String(64), nullable=True, index=True),
        sa.Column("kind", sa.String(32), nullable=False, index=True),
        sa.Column("agent", sa.String(48), nullable=False),
        sa.Column("payload", _JSON, nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, index=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("privacy_tier", sa.String(16), nullable=True),
        sa.Column("autonomy_level", sa.String(2), nullable=False, server_default="L1"),
        sa.Column("approval_id", sa.Integer(), nullable=True, index=True),
        sa.Column("result", _JSON, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(96), nullable=True),
    )
    op.create_index("ix_ai_proposals_owner_status", "ai_proposals", ["owner_id", "status"])

    op.create_table(
        "work_autonomy_grants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.String(64), nullable=False, index=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("action_kind", sa.String(32), nullable=False),
        sa.Column("level", sa.String(2), nullable=False, server_default="L1"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("owner_id", "project_id", "action_kind", name="uq_autonomy_scope"),
    )

    op.create_table(
        "work_ai_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.String(64), nullable=False, index=True),
        sa.Column("project_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.String(96), nullable=True),
        sa.UniqueConstraint("owner_id", "project_id", name="uq_ai_setting_scope"),
    )


def downgrade() -> None:
    op.drop_table("work_ai_settings")
    op.drop_table("work_autonomy_grants")
    op.drop_index("ix_ai_proposals_owner_status", table_name="ai_proposals")
    op.drop_table("ai_proposals")
