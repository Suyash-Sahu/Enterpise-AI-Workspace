"""add_workgraph

Revision ID: 20766c5d2168
Revises: e81f72d90a12
Create Date: 2026-09-14 14:24:03.662875

Scoped to only the new Project/Task/TaskDependency tables. Autogenerate also
picked up unrelated pre-existing schema drift on oauth_states/oauth_tokens/
sessions (type/constraint changes from an earlier, separate piece of work) --
stripped here, same as every prior migration in this project, so this
revision only does what its message says.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20766c5d2168'
down_revision: Union[str, Sequence[str], None] = 'e81f72d90a12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'projects',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_projects_owner_created', 'projects', ['owner_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_projects_owner_id'), 'projects', ['owner_id'], unique=False)
    op.create_index(op.f('ix_projects_status'), 'projects', ['status'], unique=False)

    op.create_table(
        'tasks',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('assignee', sa.String(length=255), nullable=True),
        sa.Column('priority', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=16), nullable=False),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('source_ref', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tasks_owner_id'), 'tasks', ['owner_id'], unique=False)
    op.create_index('ix_tasks_owner_status', 'tasks', ['owner_id', 'status'], unique=False)
    op.create_index(op.f('ix_tasks_project_id'), 'tasks', ['project_id'], unique=False)
    op.create_index(op.f('ix_tasks_status'), 'tasks', ['status'], unique=False)

    op.create_table(
        'task_dependencies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(length=64), nullable=False),
        sa.Column('depends_on_task_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['depends_on_task_id'], ['tasks.id'], ),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_task_dependencies_depends_on_task_id'), 'task_dependencies', ['depends_on_task_id'], unique=False)
    op.create_index(op.f('ix_task_dependencies_task_id'), 'task_dependencies', ['task_id'], unique=False)
    op.create_index('ix_task_deps_unique', 'task_dependencies', ['task_id', 'depends_on_task_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_task_deps_unique', table_name='task_dependencies')
    op.drop_index(op.f('ix_task_dependencies_task_id'), table_name='task_dependencies')
    op.drop_index(op.f('ix_task_dependencies_depends_on_task_id'), table_name='task_dependencies')
    op.drop_table('task_dependencies')

    op.drop_index(op.f('ix_tasks_status'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_project_id'), table_name='tasks')
    op.drop_index('ix_tasks_owner_status', table_name='tasks')
    op.drop_index(op.f('ix_tasks_owner_id'), table_name='tasks')
    op.drop_table('tasks')

    op.drop_index(op.f('ix_projects_status'), table_name='projects')
    op.drop_index(op.f('ix_projects_owner_id'), table_name='projects')
    op.drop_index('ix_projects_owner_created', table_name='projects')
    op.drop_table('projects')
