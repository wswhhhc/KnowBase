"""Enforce globally unique conversation thread identifiers.

Revision ID: 005
Revises: 004
"""

from typing import Sequence, Union

from alembic import op


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_conversations_thread_id",
        "conversations",
        ["thread_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_conversations_thread_id", table_name="conversations")
