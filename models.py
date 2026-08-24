"""
models.py — SQLAlchemy models for the Cribl Framework.
"""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class OnboardingRequest(db.Model):
    __tablename__ = "onboarding_requests"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(30), unique=True, nullable=False, index=True)
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    lan_id = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False, default="")
    last_name = db.Column(db.String(100), nullable=False, default="")
    requester_name = db.Column(db.String(200), nullable=False)
    apmid = db.Column(db.String(100), nullable=False, index=True)
    appname = db.Column(db.String(100), nullable=False)
    app_team = db.Column(db.String(200), nullable=False, default="")
    app_emails = db.Column(db.JSON, nullable=False, default=list)
    region = db.Column(db.String(10), nullable=False)
    log_destinations = db.Column(db.JSON, nullable=False, default=list)
    log_types = db.Column(db.JSON, nullable=False, default=list)
    entitlement_groups = db.Column(db.JSON, nullable=False, default=list)
    worker_group = db.Column(db.String(100), nullable=False, default="default")
    dest = db.Column(db.String(200), nullable=False, default="")
    ilm_tier = db.Column(db.String(50), nullable=False, default="none")
    kibana_dashboard = db.Column(db.String(200), nullable=True)
    logstash_pipeline = db.Column(db.String(200), nullable=True)
    roles = db.Column(db.Integer, nullable=False, default=0)
    routes = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)

    def to_dict(self):
        return {
            "req_id":             self.request_id,
            "date":               self.timestamp.isoformat() if self.timestamp else None,
            "lan_id":             self.lan_id,
            "first_name":         self.first_name,
            "last_name":          self.last_name,
            "submitted_by":       self.requester_name,
            "apm":                self.apmid,
            "name":               self.appname,
            "app_team":           self.app_team,
            "app_emails":         self.app_emails,
            "region":             self.region,
            "log_destinations":   self.log_destinations,
            "log_types":          self.log_types,
            "entitlements":       self.entitlement_groups,
            "worker_group":       self.worker_group,
            "dest":               self.dest,
            "ilm_tier":           self.ilm_tier,
            "kibana_dashboard":   self.kibana_dashboard,
            "logstash_pipeline":  self.logstash_pipeline,
            "roles":              self.roles,
            "routes":             self.routes,
            "status":             self.status,
        }
