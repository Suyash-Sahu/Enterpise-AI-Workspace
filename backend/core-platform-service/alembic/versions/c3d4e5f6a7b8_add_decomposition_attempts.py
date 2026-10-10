"""add_decomposition_attempts

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'decomposition_attempts',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('request_id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('objective_hash', sa.String(length=64), nullable=False),
        sa.Column('decomposer_mode', sa.String(length=32), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('raw_output', sa.Text(), nullable=True),
        sa.Column('accepted', sa.Boolean(), nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_decomposition_attempts_request_id'), 'decomposition_attempts', ['request_id'], unique=False)
    op.create_index(op.f('ix_decomposition_attempts_owner_id'), 'decomposition_attempts', ['owner_id'], unique=False)
    op.create_index(op.f('ix_decomposition_attempts_objective_hash'), 'decomposition_attempts', ['objective_hash'], unique=False)
    op.create_index('ix_dattempt_owner_obj', 'decomposition_attempts', ['owner_id', 'objective_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_dattempt_owner_obj', table_name='decomposition_attempts')
    op.drop_index(op.f('ix_decomposition_attempts_objective_hash'), table_name='decomposition_attempts')
    op.drop_index(op.f('ix_decomposition_attempts_owner_id'), table_name='decomposition_attempts')
    op.drop_index(op.f('ix_decomposition_attempts_request_id'), table_name='decomposition_attempts')
    op.drop_table('decomposition_attempts')
