"""add_automations

Revision ID: 45e25cdc1120
Revises: 3d16b70ee9de
Create Date: 2026-09-15 11:09:01.590989

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '45e25cdc1120'
down_revision: Union[str, Sequence[str], None] = '3d16b70ee9de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('automations',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('owner_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('trigger_type', sa.String(length=16), nullable=False),
    sa.Column('schedule', sa.String(length=128), nullable=True),
    sa.Column('condition', sa.Text(), nullable=True),
    sa.Column('task_graph_template', sa.Text(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('execution_history', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_automations_owner_enabled', 'automations', ['owner_id', 'enabled'], unique=False)
    op.create_index(op.f('ix_automations_owner_id'), 'automations', ['owner_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_automations_owner_id'), table_name='automations')
    op.drop_index('ix_automations_owner_enabled', table_name='automations')
    op.drop_table('automations')
