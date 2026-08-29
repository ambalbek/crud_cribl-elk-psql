"""Tests for the state machine, transitions, audit logging, and delivery guards."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.models import AuditLog, DeliveryJob, OnboardingRequest, RequestStatus
from app.services.state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    transition_request,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_request(
    status: RequestStatus = RequestStatus.intake_pending,
    **overrides,
) -> OnboardingRequest:
    defaults = {
        "id": uuid.uuid4(),
        "app_name": "test-app",
        "apm_id": f"APM-{uuid.uuid4().hex[:8].upper()}",
        "requestor_name": "Tester",
        "requestor_email": "tester@example.com",
        "team": "platform",
        "environment": "dev",
        "status": status,
    }
    defaults.update(overrides)
    return OnboardingRequest(**defaults)


# ── Legal transitions ───────────────────────────────────────────────────────

class TestLegalTransitions:
    """Every edge in ALLOWED_TRANSITIONS must succeed and create an audit row."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (src, dst)
            for src, dsts in ALLOWED_TRANSITIONS.items()
            for dst in dsts
        ],
        ids=lambda val: val.value if isinstance(val, RequestStatus) else str(val),
    )
    def test_legal_transition(self, app, db, from_status, to_status):
        req = _make_request(status=from_status)
        db.session.add(req)
        db.session.flush()

        audit = transition_request(req, to_status, actor="test-user")
        db.session.flush()

        assert req.status == to_status
        assert audit.stage == to_status
        assert audit.actor == "test-user"
        assert audit.outcome == "success"


# ── Illegal transitions ────────────────────────────────────────────────────

class TestIllegalTransitions:
    """Every pair NOT in ALLOWED_TRANSITIONS must raise."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (src, dst)
            for src in RequestStatus
            for dst in RequestStatus
            if dst not in ALLOWED_TRANSITIONS.get(src, [])
        ],
        ids=lambda val: val.value if isinstance(val, RequestStatus) else str(val),
    )
    def test_illegal_transition(self, app, db, from_status, to_status):
        req = _make_request(status=from_status)
        db.session.add(req)
        db.session.flush()

        with pytest.raises(InvalidTransitionError) as exc_info:
            transition_request(req, to_status, actor="test-user")

        assert exc_info.value.current == from_status
        assert exc_info.value.target == to_status
        assert req.status == from_status  # unchanged


# ── Audit log per transition ────────────────────────────────────────────────

class TestAuditLog:
    """Each successful transition writes exactly one audit row."""

    def test_audit_row_written(self, app, db):
        req = _make_request()
        db.session.add(req)
        db.session.flush()

        audit = transition_request(req, RequestStatus.intake_validated, actor="auditor")
        db.session.flush()

        rows = AuditLog.query.filter_by(request_id=req.id).all()
        assert len(rows) == 1
        assert rows[0].id == audit.id
        assert rows[0].stage == RequestStatus.intake_validated
        assert rows[0].actor == "auditor"
        assert rows[0].outcome == "success"

    def test_audit_metadata_stored(self, app, db):
        req = _make_request()
        db.session.add(req)
        db.session.flush()

        meta = {"reason": "unit test"}
        audit = transition_request(
            req,
            RequestStatus.intake_validated,
            actor="meta-tester",
            metadata=meta,
        )
        db.session.flush()

        stored = db.session.get(AuditLog, audit.id)
        assert stored.metadata_ == meta

    def test_multiple_transitions_create_multiple_rows(self, app, db):
        req = _make_request()
        db.session.add(req)
        db.session.flush()

        transition_request(req, RequestStatus.intake_validated, actor="a1")
        transition_request(req, RequestStatus.engagement, actor="a2")
        transition_request(req, RequestStatus.solutioning, actor="a3")
        db.session.flush()

        rows = AuditLog.query.filter_by(request_id=req.id).all()
        assert len(rows) == 3


# ── mark_delivery_complete guard ────────────────────────────────────────────

class TestDeliveryCompleteGuard:
    """delivery_complete must refuse while any job is pending or running."""

    def test_refuses_with_pending_job(self, client, app, db, admin_headers):
        req = _make_request(status=RequestStatus.delivery_storage)
        db.session.add(req)
        db.session.flush()

        job = DeliveryJob(
            request_id=req.id,
            job_type="cribl_edge",
            status="pending",
        )
        db.session.add(job)
        db.session.flush()

        # Transition to delivery_complete via the HTTP endpoint
        resp = client.post(
            f"/api/delivery/{req.id}/complete",
            json={"actor": "admin"},
            headers=admin_headers,
        )
        assert resp.status_code == 409
        data = resp.get_json()
        assert data.get("pending_jobs", 0) > 0

    def test_refuses_with_running_job(self, client, app, db, admin_headers):
        req = _make_request(status=RequestStatus.delivery_storage)
        db.session.add(req)
        db.session.flush()

        job = DeliveryJob(
            request_id=req.id,
            job_type="etn_portal",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(job)
        db.session.flush()

        resp = client.post(
            f"/api/delivery/{req.id}/complete",
            json={"actor": "admin"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    def test_allows_when_all_jobs_done(self, client, app, db, admin_headers):
        req = _make_request(status=RequestStatus.delivery_storage)
        db.session.add(req)
        db.session.flush()

        job = DeliveryJob(
            request_id=req.id,
            job_type="cribl_edge",
            status="success",
            completed_at=datetime.now(timezone.utc),
        )
        db.session.add(job)
        db.session.flush()

        resp = client.post(
            f"/api/delivery/{req.id}/complete",
            json={"actor": "admin"},
            headers=admin_headers,
        )
        # May be 409 if state transition from delivery_storage -> delivery_complete
        # is not allowed (it goes delivery_storage -> delivery_complete in current model).
        # Actually it IS allowed.
        assert resp.status_code == 200

    def test_allows_when_no_jobs(self, client, app, db, admin_headers):
        req = _make_request(status=RequestStatus.delivery_storage)
        db.session.add(req)
        db.session.flush()

        resp = client.post(
            f"/api/delivery/{req.id}/complete",
            json={"actor": "admin"},
            headers=admin_headers,
        )
        assert resp.status_code == 200


# ── delivery_failed transitions ─────────────────────────────────────────────

class TestDeliveryFailed:
    """delivery_failed is reachable from every delivery_* state."""

    @pytest.mark.parametrize(
        "from_status",
        [
            RequestStatus.delivery_collection,
            RequestStatus.delivery_routing,
            RequestStatus.delivery_storage,
            RequestStatus.delivery_complete,
        ],
    )
    def test_can_reach_delivery_failed(self, app, db, from_status):
        req = _make_request(status=from_status)
        db.session.add(req)
        db.session.flush()

        audit = transition_request(req, RequestStatus.delivery_failed, actor="system")
        db.session.flush()

        assert req.status == RequestStatus.delivery_failed
        assert audit.outcome == "success"

    def test_cannot_reach_delivery_failed_from_solutioning(self, app, db):
        req = _make_request(status=RequestStatus.solutioning)
        db.session.add(req)
        db.session.flush()

        with pytest.raises(InvalidTransitionError):
            transition_request(req, RequestStatus.delivery_failed, actor="system")
