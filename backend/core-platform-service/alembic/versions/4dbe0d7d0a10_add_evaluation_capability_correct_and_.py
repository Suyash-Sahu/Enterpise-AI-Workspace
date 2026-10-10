"""add_evaluation_capability_correct_and_privacy_confidence

Revision ID: 4dbe0d7d0a10
Revises: 45e25cdc1120
Create Date: 2026-09-20 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4dbe0d7d0a10'
down_revision: Union[str, Sequence[str], None] = '45e25cdc1120'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('evaluation_results', sa.Column('privacy_confidence', sa.Float(), nullable=True))
    op.add_column('evaluation_results', sa.Column('capability_correct', sa.Boolean(), nullable=True))
    op.add_column('evaluation_runs', sa.Column('artifact_error', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('evaluation_runs', 'artifact_error')
    op.drop_column('evaluation_results', 'capability_correct')
    op.drop_column('evaluation_results', 'privacy_confidence')
