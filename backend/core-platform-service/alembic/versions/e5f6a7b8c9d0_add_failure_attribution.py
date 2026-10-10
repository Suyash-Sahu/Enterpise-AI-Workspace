"""add_failure_attribution_and_replanning_strategy

Phase 30: Failure Attribution & Failure Diagnosis.

Adds:
  - `failure_attributions` table: one row per failed run recording suspect
    step, failure category (from the closed taxonomy), confidence and evidence.
  - `strategy` column on `replanning_events` (Phase 31): which recovery
    strategy was applied so effectiveness is measurable per category.
  - `attributed_step_id` on `replanning_events` (Phase 31): which step
    attribution blamed so (strategy, step) pair measurement is possible.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 30: failure_attributions table
    op.create_table(
        "failure_attributions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("plan_id", sa.String(64), sa.ForeignKey("workflow_plans.id"), nullable=False),
        sa.Column("suspect_step_id", sa.String(32), nullable=False),
        sa.Column("suspect_capability", sa.String(64), nullable=False),
        sa.Column("failure_category", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_failure_attributions_plan", "failure_attributions", ["plan_id"])

    # Phase 31: extend replanning_events with strategy fields
    op.add_column(
        "replanning_events",
        sa.Column("strategy", sa.String(64), nullable=True),
    )
    op.add_column(
        "replanning_events",
        sa.Column("attributed_step_id", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("replanning_events", "attributed_step_id")
    op.drop_column("replanning_events", "strategy")
    op.drop_index("ix_failure_attributions_plan", table_name="failure_attributions")
    op.drop_table("failure_attributions")
