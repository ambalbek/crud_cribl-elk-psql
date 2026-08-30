import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, String, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.extensions import db


class RequestStatus(str, enum.Enum):
    intake_pending = "intake_pending"
    intake_validated = "intake_validated"
    engagement = "engagement"
    solutioning = "solutioning"
    # Correct delivery order: storage verified before anything is built
    storage_pending = "storage_pending"
    storage_confirmed = "storage_confirmed"
    delivery_destination = "delivery_destination"
    delivery_pack = "delivery_pack"
    delivery_route = "delivery_route"
    delivery_collection = "delivery_collection"
    # Legacy aliases kept for DB compatibility
    delivery_routing = "delivery_routing"
    delivery_storage = "delivery_storage"
    delivery_complete = "delivery_complete"
    delivery_failed = "delivery_failed"
    validation = "validation"
    reverify = "reverify"
    complete = "complete"
    cancelled = "cancelled"


class OnboardingRequest(db.Model):
    __tablename__ = "onboarding_requests"

    id = db.Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Identity ─────────────────────────────────────────────────
    app_name = db.Column(String(256), nullable=False)
    apm_id = db.Column(String(128), unique=True, nullable=False)
    lan_id = db.Column(String(128), nullable=True)
    first_name = db.Column(String(128), nullable=True)
    last_name = db.Column(String(128), nullable=True)
    requestor_name = db.Column(String(256), nullable=False)
    requestor_email = db.Column(String(320), nullable=False)
    team = db.Column(String(256), nullable=False)
    app_emails = db.Column(JSONB, nullable=True, default=list)

    # ── Workspace & routing ──────────────────────────────────────
    environment = db.Column(
        Enum("dev", "stage", "prod", name="environment_enum", create_type=False),
        nullable=False,
    )
    workspace = db.Column(String(64), nullable=True)
    worker_group = db.Column(String(128), nullable=True)
    region = db.Column(String(16), nullable=True)

    # ── Log configuration ────────────────────────────────────────
    data_type = db.Column(String(64), nullable=True)
    log_destinations = db.Column(JSONB, nullable=True, default=list)
    log_types = db.Column(JSONB, nullable=True, default=list)
    ilm_tier = db.Column(String(32), nullable=True, default="none")

    # ── Entitlements ─────────────────────────────────────────────
    entitlement_groups = db.Column(JSONB, nullable=True, default=list)

    # ── Pack (resolved at intake, pinned) ────────────────────────
    pack_id = db.Column(String(128), nullable=True)
    pack_version = db.Column(String(32), nullable=True)

    # ── Storage gate ─────────────────────────────────────────────
    storage_container = db.Column(String(256), nullable=True)
    storage_prefix = db.Column(String(256), nullable=True)
    storage_region = db.Column(String(64), nullable=True)
    storage_verified_at = db.Column(DateTime(timezone=True), nullable=True)
    storage_verified_by = db.Column(String(256), nullable=True)

    # ── State ────────────────────────────────────────────────────
    status = db.Column(
        Enum(RequestStatus, name="request_status_enum", create_type=False),
        nullable=False,
        default=RequestStatus.intake_pending,
    )

    # ── Flexible data (solutioning workbook, entity mapping, etc.)
    form_data = db.Column(JSONB, nullable=True, default=dict)
    entity_mapping = db.Column(JSONB, nullable=True, default=dict)
    workbook_data = db.Column(JSONB, nullable=True, default=dict)

    # ── Timestamps ───────────────────────────────────────────────
    created_at = db.Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    audit_logs = relationship(
        "AuditLog", back_populates="request", cascade="all, delete-orphan"
    )
    delivery_jobs = relationship(
        "DeliveryJob", back_populates="request", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<OnboardingRequest {self.apm_id} [{self.status.value}]>"
