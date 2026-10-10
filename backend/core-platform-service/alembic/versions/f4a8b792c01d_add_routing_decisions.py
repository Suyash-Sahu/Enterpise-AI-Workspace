"""add_routing_decisions

Revision ID: f4a8b792c01d
Revises: ecc3ac0d1b7a
Create Date: 2026-09-14 12:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a8b792c01d'
down_revision: Union[str, Sequence[str], None] = 'ecc3ac0d1b7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'routing_decisions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('workflow_step_id', sa.String(length=64), nullable=False),
        sa.Column('placement', sa.String(length=32), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('privacy_label', sa.String(length=32), nullable=False),
        sa.Column('classification_confidence', sa.Float(), nullable=False),
        sa.Column('classification_stage', sa.String(length=64), nullable=True),
        sa.Column('predicted_quality', sa.Float(), nullable=False),
        sa.Column('predicted_latency_ms', sa.Float(), nullable=False),
        sa.Column('predicted_cost_usd', sa.Float(), nullable=False),
        sa.Column('risk', sa.Float(), nullable=False),
        sa.Column('routing_confidence', sa.Float(), nullable=False),
        sa.Column('constraint_binding', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workflow_step_id'], ['workflow_steps.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_routing_decisions_workflow_step_id'), 'routing_decisions', ['workflow_step_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_routing_decisions_workflow_step_id'), table_name='routing_decisions')
    op.drop_table('routing_decisions')
