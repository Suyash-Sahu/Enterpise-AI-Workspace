"""add_commitments

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-24 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('commitments',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('owner_id', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('responsible_party', sa.String(length=255), nullable=True),
    sa.Column('due_date', sa.String(length=128), nullable=True),
    sa.Column('source_type', sa.String(length=16), nullable=False),
    sa.Column('source_ref', sa.String(length=128), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('linked_task_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['linked_task_id'], ['tasks.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('owner_id', 'source_type', 'source_ref', name='uq_commitment_source'),
    )
    op.create_index(op.f('ix_commitments_owner_id'), 'commitments', ['owner_id'], unique=False)
    op.create_index(op.f('ix_commitments_status'), 'commitments', ['status'], unique=False)
    op.create_index('ix_commitments_owner_status', 'commitments', ['owner_id', 'status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_commitments_owner_status', table_name='commitments')
    op.drop_index(op.f('ix_commitments_status'), table_name='commitments')
    op.drop_index(op.f('ix_commitments_owner_id'), table_name='commitments')
    op.drop_table('commitments')
