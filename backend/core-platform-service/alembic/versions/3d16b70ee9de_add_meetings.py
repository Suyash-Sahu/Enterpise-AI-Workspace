"""add_meetings

Revision ID: 3d16b70ee9de
Revises: 20766c5d2168
Create Date: 2026-09-15 10:08:19.358696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3d16b70ee9de'
down_revision: Union[str, Sequence[str], None] = '20766c5d2168'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('meetings',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('owner_id', sa.String(length=64), nullable=False),
    sa.Column('transcript_source', sa.String(length=32), nullable=False),
    sa.Column('transcript_text', sa.Text(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('extraction_json', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_meetings_owner_created', 'meetings', ['owner_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_meetings_owner_id'), 'meetings', ['owner_id'], unique=False)
    op.create_index(op.f('ix_meetings_status'), 'meetings', ['status'], unique=False)
    op.create_table('meeting_action_items',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('meeting_id', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('owner', sa.String(length=255), nullable=True),
    sa.Column('due_date', sa.String(length=128), nullable=True),
    sa.Column('workgraph_task_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
    sa.ForeignKeyConstraint(['workgraph_task_id'], ['tasks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_meeting_action_items_meeting_id'), 'meeting_action_items', ['meeting_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_meeting_action_items_meeting_id'), table_name='meeting_action_items')
    op.drop_table('meeting_action_items')
    op.drop_index(op.f('ix_meetings_status'), table_name='meetings')
    op.drop_index(op.f('ix_meetings_owner_id'), table_name='meetings')
    op.drop_index('ix_meetings_owner_created', table_name='meetings')
    op.drop_table('meetings')
