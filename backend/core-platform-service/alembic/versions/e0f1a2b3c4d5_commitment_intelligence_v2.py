"""commitment_intelligence_v2

Revision ID: e0f1a2b3c4d5
Revises: d9e8f7a6b5c4
Create Date: 2026-11-03 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'd9e8f7a6b5c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add fields to commitments table
    op.add_column('commitments', sa.Column('direction', sa.String(length=32), server_default='owed_by_me', nullable=False))
    op.add_column('commitments', sa.Column('counterparty', sa.String(length=255), nullable=True))
    op.add_column('commitments', sa.Column('original_due_date_text', sa.String(length=255), nullable=True))
    op.add_column('commitments', sa.Column('normalized_due_date', sa.DateTime(), nullable=True))
    op.add_column('commitments', sa.Column('timezone', sa.String(length=64), server_default='UTC', nullable=True))
    op.add_column('commitments', sa.Column('confidence', sa.Float(), server_default='1.0', nullable=True))
    op.add_column('commitments', sa.Column('evidence', sa.Text(), nullable=True))
    op.add_column('commitments', sa.Column('priority', sa.String(length=16), server_default='medium', nullable=False))
    op.add_column('commitments', sa.Column('source_metadata', sa.Text(), nullable=True))
    op.add_column('commitments', sa.Column('verification_status', sa.String(length=32), server_default='unverified', nullable=False))
    op.add_column('commitments', sa.Column('verification_evidence', sa.Text(), nullable=True))
    op.add_column('commitments', sa.Column('verification_reasoning', sa.Text(), nullable=True))
    op.add_column('commitments', sa.Column('review_required', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    op.create_index('ix_commitments_owner_direction', 'commitments', ['owner_id', 'direction'], unique=False)
    op.create_index('ix_commitments_owner_due', 'commitments', ['owner_id', 'normalized_due_date'], unique=False)

    # 2. Create commitment_runs table
    op.create_table(
        'commitment_runs',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('run_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='queued', nullable=False),
        sa.Column('current_stage', sa.String(length=64), nullable=True),
        sa.Column('progress_percent', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_items', sa.Integer(), server_default='0', nullable=False),
        sa.Column('processed_items', sa.Integer(), server_default='0', nullable=False),
        sa.Column('successful_items', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed_items', sa.Integer(), server_default='0', nullable=False),
        sa.Column('commitments_found', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('updated_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('warnings', sa.Text(), nullable=True),
        sa.Column('errors', sa.Text(), nullable=True),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('cancel_requested', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_commitment_runs_owner_id'), 'commitment_runs', ['owner_id'], unique=False)
    op.create_index(op.f('ix_commitment_runs_status'), 'commitment_runs', ['status'], unique=False)
    op.create_index('ix_commitment_runs_owner_status', 'commitment_runs', ['owner_id', 'status'], unique=False)
    op.create_index('ix_commitment_runs_owner_created', 'commitment_runs', ['owner_id', 'created_at'], unique=False)

    # 3. Create commitment_run_stages table
    op.create_table(
        'commitment_run_stages',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('stage_name', sa.String(length=64), nullable=False),
        sa.Column('stage_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='pending', nullable=False),
        sa.Column('progress_percent', sa.Integer(), server_default='0', nullable=False),
        sa.Column('processed_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['commitment_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_commitment_run_stages_run_id'), 'commitment_run_stages', ['run_id'], unique=False)

    # 4. Create commitment_events table
    op.create_table(
        'commitment_events',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('commitment_id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('actor_id', sa.String(length=64), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['commitment_id'], ['commitments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_commitment_events_commitment_id'), 'commitment_events', ['commitment_id'], unique=False)
    op.create_index(op.f('ix_commitment_events_owner_id'), 'commitment_events', ['owner_id'], unique=False)
    op.create_index(op.f('ix_commitment_events_created_at'), 'commitment_events', ['created_at'], unique=False)
    op.create_index('ix_commitment_events_commit_created', 'commitment_events', ['commitment_id', 'created_at'], unique=False)
    op.create_index('ix_commitment_events_owner_type', 'commitment_events', ['owner_id', 'event_type'], unique=False)


def downgrade() -> None:
    op.drop_table('commitment_events')
    op.drop_table('commitment_run_stages')
    op.drop_table('commitment_runs')

    op.drop_index('ix_commitments_owner_due', table_name='commitments')
    op.drop_index('ix_commitments_owner_direction', table_name='commitments')

    op.drop_column('commitments', 'review_required')
    op.drop_column('commitments', 'verification_reasoning')
    op.drop_column('commitments', 'verification_evidence')
    op.drop_column('commitments', 'verification_status')
    op.drop_column('commitments', 'source_metadata')
    op.drop_column('commitments', 'priority')
    op.drop_column('commitments', 'evidence')
    op.drop_column('commitments', 'confidence')
    op.drop_column('commitments', 'timezone')
    op.drop_column('commitments', 'normalized_due_date')
    op.drop_column('commitments', 'original_due_date_text')
    op.drop_column('commitments', 'counterparty')
    op.drop_column('commitments', 'direction')

