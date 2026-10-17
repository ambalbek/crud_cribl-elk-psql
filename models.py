"""
models.py — SQLAlchemy models for the Cribl Framework.

Maps to the etn_onboarding table schema (UUID primary key, apm_id column).
"""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

db = SQLAlchemy()


class OnboardingRequest(db.Model):
    __tablename__ = "onboarding_requests"

    id = db.Column(PG_UUID(as_uuid=True), primary_key=True)
    app_name = db.Column(db.String(256), nullable=False)
    apm_id = db.Column(db.String(128), unique=True, nullable=False, index=True)
    requestor_name = db.Column(db.String(256), nullable=False, default="")
    requestor_email = db.Column(db.String(320), nullable=False, default="")
    team = db.Column(db.String(256), nullable=False, default="")
    lan_id = db.Column(db.String(128), nullable=True)
    first_name = db.Column(db.String(128), nullable=True)
    last_name = db.Column(db.String(128), nullable=True)
    app_emails = db.Column(db.JSON, nullable=True, default=list)
    environment = db.Column(db.JSON, nullable=False, default=list)
    region = db.Column(db.String(16), nullable=True)
    data_type = db.Column(db.String(64), nullable=True)
    log_destinations = db.Column(db.JSON, nullable=True, default=list)
    log_types = db.Column(db.JSON, nullable=True, default=list)
    ilm_tier = db.Column(db.String(32), nullable=True, default="none")
    entitlement_groups = db.Column(db.JSON, nullable=True, default=list)
    pack_id = db.Column(db.String(128), nullable=True)
    pack_version = db.Column(db.String(32), nullable=True)
    form_data = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="intake_pending", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Storage fields
    storage_container = db.Column(db.String(256), nullable=True)
    storage_prefix = db.Column(db.String(256), nullable=True)
    storage_region = db.Column(db.String(64), nullable=True)
    storage_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    storage_verified_by = db.Column(db.String(256), nullable=True)

    # Cribl enrichment fields
    dest = db.Column(db.String(200), nullable=True, default="")
    elk_capacity = db.Column(db.JSON, nullable=True)
    kibana_dashboard = db.Column(db.String(200), nullable=True)
    logstash_pipeline = db.Column(db.String(200), nullable=True)
    roles = db.Column(db.Integer, nullable=True, default=0)
    routes = db.Column(db.Integer, nullable=True, default=0)
    ays_group = db.Column(db.String(200), nullable=True)

    def to_dict(self):
        return {
            "req_id":             str(self.id),
            "date":               self.created_at.isoformat() if self.created_at else None,
            "lan_id":             self.lan_id or "",
            "first_name":         self.first_name or "",
            "last_name":          self.last_name or "",
            "submitted_by":       self.requestor_name or "",
            "apm":                self.apm_id,
            "name":               self.app_name,
            "team":               self.team or "",
            "ays_group":          self.ays_group or "",
            "app_emails":         self.app_emails or [],
            "region":             self.region or "",
            "log_destinations":   self.log_destinations or [],
            "log_types":          self.log_types or [],
            "entitlements":       self.entitlement_groups or [],
            "environment":        self.environment or [],
            "data_type":          self.data_type or "",
            "dest":               self.dest or "",
            "ilm_tier":           self.ilm_tier or "none",
            "elk_capacity":       self.elk_capacity,
            "kibana_dashboard":   self.kibana_dashboard,
            "logstash_pipeline":  self.logstash_pipeline,
            "roles":              self.roles or 0,
            "routes":             self.routes or 0,
            "status":             self.status,
        }
