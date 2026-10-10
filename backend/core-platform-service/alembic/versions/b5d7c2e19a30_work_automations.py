"""AMOF Work stage 7: work_automations, work_automation_runs, work_automation_fired

Revision ID: b5d7c2e19a30
Revises: 9e3a71c5d0b4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "b5d7c2e19a30"
down_revision = "9e3a71c5d0b4"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "work_automations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, index=True),
        sa.Column("project_id", sa.String(64), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("trigger", _JSON, nullable=False),
        sa.Column("conditions", _JSON, nullable=False),
        sa.Column("actions", _JSON, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, index=True),
        sa.Column("definition_hash", sa.String(64), nullable=False),
        sa.Column("previewed_hash", sa.String(64), nullable=True),
        sa.Column("previewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "work_automation_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("automation_id", sa.String(64), nullable=False, index=True),
        sa.Column("owner_id", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("proposals_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detail", _JSON, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), index=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "work_automation_fired",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("automation_id", sa.String(64), nullable=False, index=True),
        sa.Column("task_id", sa.String(64), nullable=False),
        sa.Column("trigger_key", sa.String(96), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("automation_id", "task_id", "trigger_key", name="uq_automation_fired"),
    )


def downgrade() -> None:
    op.drop_table("work_automation_fired")
    op.drop_table("work_automation_runs")
    op.drop_table("work_automations")
