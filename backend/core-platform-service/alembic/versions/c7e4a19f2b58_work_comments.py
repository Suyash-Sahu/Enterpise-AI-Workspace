"""AMOF Work stage 8: work_item_comments

Revision ID: c7e4a19f2b58
Revises: b5d7c2e19a30
"""
from alembic import op
import sqlalchemy as sa

revision = "c7e4a19f2b58"
down_revision = "b5d7c2e19a30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_item_comments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, index=True),
        sa.Column("task_id", sa.String(64), nullable=False, index=True),
        sa.Column("author", sa.String(96), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_comments_owner_task_created", "work_item_comments", ["owner_id", "task_id", "created_at"])


def downgrade() -> None:
    op.drop_table("work_item_comments")
