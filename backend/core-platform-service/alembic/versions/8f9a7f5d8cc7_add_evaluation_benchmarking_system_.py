"""add evaluation benchmarking system nullable updates

Revision ID: 8f9a7f5d8cc7
Revises: a3ffdde2df9e
Create Date: 2026-08-11 13:08:45.453477

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8f9a7f5d8cc7'
down_revision: Union[str, Sequence[str], None] = 'a3ffdde2df9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('evaluation_metrics', sa.Column('metric_status', sa.String(length=32), nullable=False, server_default='AVAILABLE'))
    op.alter_column('evaluation_metrics', 'metric_value',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.add_column('evaluation_results', sa.Column('execution_blocked', sa.Boolean(), nullable=True))
    op.add_column('evaluation_results', sa.Column('approval_guard_triggered', sa.Boolean(), nullable=True))
    op.add_column('evaluation_runs', sa.Column('configuration_hash', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_eval_tasks_run_task', 'evaluation_tasks', ['run_id', 'task_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_eval_tasks_run_task', 'evaluation_tasks', type_='unique')
    op.drop_column('evaluation_runs', 'configuration_hash')
    op.drop_column('evaluation_results', 'approval_guard_triggered')
    op.drop_column('evaluation_results', 'execution_blocked')
    op.alter_column('evaluation_metrics', 'metric_value',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.drop_column('evaluation_metrics', 'metric_status')
