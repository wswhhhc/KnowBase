"""Add jobs schema.

Revision ID: 003
Revises: 002
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Text(), nullable=True),
        sa.Column("workspace_id", sa.Text(), server_default=sa.text("''")),
        sa.Column("progress_json", sa.Text(), server_default=sa.text("'{}'")),
        sa.Column("error", sa.Text(), server_default=sa.text("''")),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0")),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'canceled')",
            name="ck_jobs_status",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_jobs_owner_created", "jobs", ["created_by_user_id", "created_at"])
    op.create_index("idx_jobs_status_created", "jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_jobs_status_created", table_name="jobs")
    op.drop_index("idx_jobs_owner_created", table_name="jobs")
    op.drop_table("jobs")
