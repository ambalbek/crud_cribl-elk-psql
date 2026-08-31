"""Add pack_registry table and pack columns on onboarding_requests

Revision ID: 004_pack_registry
Revises: 003_add_all_intake_columns
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004_pack_registry"
down_revision = "003_add_all_intake_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pack_registry table ──────────────────────────────────────
    op.create_table(
        "pack_registry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("data_type", sa.String(64), unique=True, nullable=False),
        sa.Column("pack_id", sa.String(128), nullable=False),
        sa.Column("pack_version", sa.String(32), nullable=False),
        sa.Column("attachment", sa.String(16), nullable=False, server_default="route"),
        sa.Column("source_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="approved"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── Seed: 'other' fallback + known data types ────────────────
    op.execute("""
        INSERT INTO pack_registry (id, data_type, pack_id, pack_version, attachment, status, notes)
        VALUES
            (gen_random_uuid(), 'other',      'passthru',       '1.0.0', 'route', 'approved', 'Fallback — unknown data types pass through unmodified'),
            (gen_random_uuid(), 'mulesoft',   'mulesoft_pack',  '1.0.0', 'route', 'approved', 'Mulesoft log processing pack'),
            (gen_random_uuid(), 'forgerock',  'forgerock_pack', '1.0.0', 'route', 'approved', 'ForgeRock log processing pack'),
            (gen_random_uuid(), 'dynatrace', 'dynatrace_pack','1.0.0', 'route', 'approved', 'Spring Boot log processing pack')
        ON CONFLICT (data_type) DO NOTHING;
    """)

    # ── Pack columns on onboarding_requests ──────────────────────
    op.add_column("onboarding_requests", sa.Column("pack_id", sa.String(128), nullable=True))
    op.add_column("onboarding_requests", sa.Column("pack_version", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("onboarding_requests", "pack_version")
    op.drop_column("onboarding_requests", "pack_id")
    op.drop_table("pack_registry")
