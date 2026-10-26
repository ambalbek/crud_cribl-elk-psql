"""Drop workspace and worker_group columns, convert environment to JSONB array

Revision ID: 006_drop_workspace_worker_group
Revises: 005_storage_gate
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "006_drop_workspace_worker_group"
down_revision = "005_storage_gate"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() is not None


def _column_type(table: str, column: str) -> str:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    row = result.fetchone()
    return (row[0] if row else "").lower()


def upgrade() -> None:
    if _column_exists("onboarding_requests", "workspace"):
        op.drop_column("onboarding_requests", "workspace")
    if _column_exists("onboarding_requests", "worker_group"):
        op.drop_column("onboarding_requests", "worker_group")

    # Convert environment from varchar to JSONB array — skip if already JSONB
    col_type = _column_type("onboarding_requests", "environment")
    if col_type and col_type not in ("jsonb", "json"):
        op.execute(
            "ALTER TABLE onboarding_requests "
            "ALTER COLUMN environment TYPE jsonb "
            "USING jsonb_build_array(environment)"
        )


def downgrade() -> None:
    # Convert environment back to varchar (take first element)
    op.execute(
        "ALTER TABLE onboarding_requests "
        "ALTER COLUMN environment TYPE varchar "
        "USING (environment->>0)"
    )
    op.add_column("onboarding_requests", sa.Column("worker_group", sa.String(128), nullable=True))
    op.add_column("onboarding_requests", sa.Column("workspace", sa.String(64), nullable=True))
