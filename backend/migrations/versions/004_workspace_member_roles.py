"""Restrict workspace member roles to editor and viewer.

Revision ID: 004
Revises: 003
"""

from typing import Sequence, Union

from alembic import op


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE workspace_members SET role = 'editor' WHERE role = 'admin'")
    with op.batch_alter_table("workspace_members") as batch_op:
        batch_op.drop_constraint("ck_workspace_members_role", type_="check")
        batch_op.create_check_constraint("ck_workspace_members_role", "role IN ('editor', 'viewer')")


def downgrade() -> None:
    with op.batch_alter_table("workspace_members") as batch_op:
        batch_op.drop_constraint("ck_workspace_members_role", type_="check")
        batch_op.create_check_constraint("ck_workspace_members_role", "role IN ('admin', 'editor', 'viewer')")
