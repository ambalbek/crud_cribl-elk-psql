import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.extensions import db


class PackRegistry(db.Model):
    __tablename__ = "pack_registry"

    id = db.Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    data_type = db.Column(String(64), unique=True, nullable=False)
    pack_id = db.Column(String(128), nullable=False)
    pack_version = db.Column(String(32), nullable=False)
    attachment = db.Column(String(16), nullable=False, default="route")
    source_id = db.Column(String(128), nullable=True)
    status = db.Column(String(16), nullable=False, default="approved")
    notes = db.Column(Text, nullable=True)
    created_at = db.Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<PackRegistry {self.data_type} -> {self.pack_id}:{self.pack_version} [{self.status}]>"
