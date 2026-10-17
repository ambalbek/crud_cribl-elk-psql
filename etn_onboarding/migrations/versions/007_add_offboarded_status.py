"""Add offboarded status to request_status_enum

Revision ID: 007_add_offboarded_status
Revises: 006_drop_workspace_worker_group
Create Date: 2026-10-17
"""
from alembic import op

revision = "007_add_offboarded_status"
down_revision = "006_drop_workspace_worker_group"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE request_status_enum ADD VALUE IF NOT EXISTS 'offboarded'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum.
    pass
