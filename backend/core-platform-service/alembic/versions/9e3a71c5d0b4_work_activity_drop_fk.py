"""AMOF Work: work_item_activity.task_id is not a foreign key (audit trail outlives tasks)

Revision ID: 9e3a71c5d0b4
Revises: 8d2f0a51c3be
"""
from alembic import op
import sqlalchemy as sa

revision = "9e3a71c5d0b4"
down_revision = "8d2f0a51c3be"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh databases already skip the FK (7c1e9d40b2aa no longer creates it);
    # databases migrated earlier still have it, so drop it only if present.
    insp = sa.inspect(op.get_bind())
    for fk in insp.get_foreign_keys("work_item_activity"):
        if fk["referred_table"] == "tasks" and fk.get("name"):
            op.drop_constraint(fk["name"], "work_item_activity", type_="foreignkey")


def downgrade() -> None:
    pass  # intentionally not restored: the FK is what broke task deletion
