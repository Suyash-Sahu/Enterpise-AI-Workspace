"""add evaluation benchmarking system

Revision ID: a3ffdde2df9e
Revises: b934c6930a4f
Create Date: 2026-08-11 12:34:19.711124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3ffdde2df9e'
down_revision: Union[str, Sequence[str], None] = 'b934c6930a4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create P10 evaluation benchmarking tables ONLY."""
    op.create_table('evaluation_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('dataset_version', sa.String(length=64), nullable=False),
    sa.Column('dataset_hash', sa.String(length=64), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('task_count', sa.Integer(), nullable=True),
    sa.Column('completed_count', sa.Integer(), nullable=True),
    sa.Column('failed_count', sa.Integer(), nullable=True),
    sa.Column('configuration_json', sa.JSON(), nullable=True),
    sa.Column('git_commit', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_runs_id'), 'evaluation_runs', ['id'], unique=False)
    op.create_index(op.f('ix_evaluation_runs_run_id'), 'evaluation_runs', ['run_id'], unique=True)
    op.create_index(op.f('ix_evaluation_runs_status'), 'evaluation_runs', ['status'], unique=False)

    op.create_table('evaluation_metrics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('metric_name', sa.String(length=64), nullable=False),
    sa.Column('metric_value', sa.Float(), nullable=False),
    sa.Column('denominator', sa.Float(), nullable=True),
    sa.Column('numerator', sa.Float(), nullable=True),
    sa.Column('metric_metadata', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['evaluation_runs.run_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_metrics_id'), 'evaluation_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_evaluation_metrics_metric_name'), 'evaluation_metrics', ['metric_name'], unique=False)
    op.create_index(op.f('ix_evaluation_metrics_run_id'), 'evaluation_metrics', ['run_id'], unique=False)

    op.create_table('evaluation_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('task_id', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('actual_capability', sa.String(length=64), nullable=True),
    sa.Column('actual_execution_mode', sa.String(length=32), nullable=True),
    sa.Column('actual_model', sa.String(length=64), nullable=True),
    sa.Column('routing_correct', sa.Boolean(), nullable=True),
    sa.Column('approval_required', sa.Boolean(), nullable=True),
    sa.Column('approval_status', sa.String(length=32), nullable=True),
    sa.Column('cache_hit', sa.Boolean(), nullable=True),
    sa.Column('verification_status', sa.String(length=32), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('latency_ms', sa.Float(), nullable=True),
    sa.Column('input_tokens', sa.Integer(), nullable=True),
    sa.Column('output_tokens', sa.Integer(), nullable=True),
    sa.Column('total_tokens', sa.Integer(), nullable=True),
    sa.Column('estimated_cost', sa.Float(), nullable=True),
    sa.Column('privacy_classification', sa.String(length=32), nullable=True),
    sa.Column('cloud_execution', sa.Boolean(), nullable=True),
    sa.Column('completion_success', sa.Boolean(), nullable=True),
    sa.Column('output_quality_score', sa.Float(), nullable=True),
    sa.Column('error_type', sa.String(length=128), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('trace_json', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['evaluation_runs.run_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_results_id'), 'evaluation_results', ['id'], unique=False)
    op.create_index(op.f('ix_evaluation_results_run_id'), 'evaluation_results', ['run_id'], unique=False)
    op.create_index(op.f('ix_evaluation_results_task_id'), 'evaluation_results', ['task_id'], unique=False)

    op.create_table('evaluation_tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('task_id', sa.String(length=64), nullable=False),
    sa.Column('task_text', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('complexity', sa.String(length=32), nullable=False),
    sa.Column('privacy_level', sa.String(length=32), nullable=False),
    sa.Column('expected_capability', sa.String(length=64), nullable=False),
    sa.Column('expected_execution_mode', sa.String(length=32), nullable=False),
    sa.Column('expected_approval', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['evaluation_runs.run_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_tasks_id'), 'evaluation_tasks', ['id'], unique=False)
    op.create_index(op.f('ix_evaluation_tasks_run_id'), 'evaluation_tasks', ['run_id'], unique=False)
    op.create_index(op.f('ix_evaluation_tasks_task_id'), 'evaluation_tasks', ['task_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_evaluation_tasks_task_id'), table_name='evaluation_tasks')
    op.drop_index(op.f('ix_evaluation_tasks_run_id'), table_name='evaluation_tasks')
    op.drop_index(op.f('ix_evaluation_tasks_id'), table_name='evaluation_tasks')
    op.drop_table('evaluation_tasks')

    op.drop_index(op.f('ix_evaluation_results_task_id'), table_name='evaluation_results')
    op.drop_index(op.f('ix_evaluation_results_run_id'), table_name='evaluation_results')
    op.drop_index(op.f('ix_evaluation_results_id'), table_name='evaluation_results')
    op.drop_table('evaluation_results')

    op.drop_index(op.f('ix_evaluation_metrics_run_id'), table_name='evaluation_metrics')
    op.drop_index(op.f('ix_evaluation_metrics_metric_name'), table_name='evaluation_metrics')
    op.drop_index(op.f('ix_evaluation_metrics_id'), table_name='evaluation_metrics')
    op.drop_table('evaluation_metrics')

    op.drop_index(op.f('ix_evaluation_runs_status'), table_name='evaluation_runs')
    op.drop_index(op.f('ix_evaluation_runs_run_id'), table_name='evaluation_runs')
    op.drop_index(op.f('ix_evaluation_runs_id'), table_name='evaluation_runs')
    op.drop_table('evaluation_runs')
