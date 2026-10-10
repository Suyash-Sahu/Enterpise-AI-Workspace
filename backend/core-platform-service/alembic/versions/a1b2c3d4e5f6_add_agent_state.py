"""add_agent_state

Revision ID: a1b2c3d4e5f6
Revises: 4dbe0d7d0a10
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4dbe0d7d0a10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'agent_state_entries',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value_json', sa.Text(), nullable=False),
        sa.Column('written_by_step', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agent_state_entries_run_id'), 'agent_state_entries', ['run_id'], unique=False)
    op.create_index(op.f('ix_agent_state_entries_owner_id'), 'agent_state_entries', ['owner_id'], unique=False)
    op.create_index(op.f('ix_agent_state_entries_created_at'), 'agent_state_entries', ['created_at'], unique=False)
    op.create_index('ix_agent_state_run_key', 'agent_state_entries', ['run_id', 'key'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_agent_state_run_key', table_name='agent_state_entries')
    op.drop_index(op.f('ix_agent_state_entries_created_at'), table_name='agent_state_entries')
    op.drop_index(op.f('ix_agent_state_entries_owner_id'), table_name='agent_state_entries')
    op.drop_index(op.f('ix_agent_state_entries_run_id'), table_name='agent_state_entries')
    op.drop_table('agent_state_entries')
