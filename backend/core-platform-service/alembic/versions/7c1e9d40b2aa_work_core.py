"""AMOF Work stage 1: work item provenance fields, dependency kind, activity log

Revision ID: 7c1e9d40b2aa
Revises: f6a7b8c9d0e1
"""
from alembic import op
import sqlalchemy as sa

revision = "7c1e9d40b2aa"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as b:
        b.add_column(sa.Column("type", sa.String(16), nullable=False, server_default="TASK"))
        b.add_column(sa.Column("created_by_actor", sa.String(96), nullable=True))
        b.add_column(sa.Column("ai_confidence", sa.Float(), nullable=True))
    with op.batch_alter_table("task_dependencies") as b:
        b.add_column(sa.Column("kind", sa.String(16), nullable=False, server_default="BLOCKED_BY"))
    op.create_table(
        "work_item_activity",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.String(64), nullable=False, index=True),
        sa.Column("task_id", sa.String(64), nullable=False, index=True),  # no FK: audit trail outlives tasks
        sa.Column("actor", sa.String(96), nullable=False),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), index=True),
    )
    op.create_index("ix_activity_owner_task_created", "work_item_activity", ["owner_id", "task_id", "created_at"])


def downgrade() -> None:
    op.drop_table("work_item_activity")
    with op.batch_alter_table("task_dependencies") as b:
        b.drop_column("kind")
    with op.batch_alter_table("tasks") as b:
        b.drop_column("ai_confidence")
        b.drop_column("created_by_actor")
        b.drop_column("type")
