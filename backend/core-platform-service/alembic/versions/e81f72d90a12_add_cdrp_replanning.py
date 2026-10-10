"""add_cdrp_replanning

Revision ID: e81f72d90a12
Revises: f4a8b792c01d
Create Date: 2026-09-14 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e81f72d90a12'
down_revision: Union[str, Sequence[str], None] = 'f4a8b792c01d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workflow_steps', sa.Column('replanning_of', sa.String(length=64), nullable=True))
    op.create_foreign_key('fk_workflow_steps_replanning_of', 'workflow_steps', 'workflow_steps', ['replanning_of'], ['id'])

    op.create_table(
        'replanning_events',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('original_step_id', sa.String(length=64), nullable=False),
        sa.Column('new_step_id', sa.String(length=64), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('confidence_before', sa.Float(), nullable=False),
        sa.Column('confidence_after', sa.Float(), nullable=True),
        sa.Column('cost_delta', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['new_step_id'], ['workflow_steps.id'], ),
        sa.ForeignKeyConstraint(['original_step_id'], ['workflow_steps.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_replanning_events_new_step_id'), 'replanning_events', ['new_step_id'], unique=False)
    op.create_index(op.f('ix_replanning_events_original_step_id'), 'replanning_events', ['original_step_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_replanning_events_original_step_id'), table_name='replanning_events')
    op.drop_index(op.f('ix_replanning_events_new_step_id'), table_name='replanning_events')
    op.drop_table('replanning_events')
    op.drop_constraint('fk_workflow_steps_replanning_of', 'workflow_steps', type_='foreignkey')
    op.drop_column('workflow_steps', 'replanning_of')
