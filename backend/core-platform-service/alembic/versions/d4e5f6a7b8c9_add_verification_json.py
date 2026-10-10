"""add_verification_json_to_workflow_steps

Phase 29: Per-Agent / Per-Step Verification.

Adds `verification_json` (TEXT, nullable) to `workflow_steps` so each step's
VerificationReport is persisted alongside its result.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-22
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
# Originally revised b2c3d4e5f6a7, which forked the migration chain with
# Phase 28's c3d4e5f6a7b8 (also a child of b2c3d4e5f6a7) -- two heads, so
# `alembic upgrade head` applied only one of them and verification_json was
# never created on databases that had taken the Phase 28 branch. Re-parented
# onto the Phase 28 head to restore a single linear chain.
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_steps",
        sa.Column("verification_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_steps", "verification_json")
