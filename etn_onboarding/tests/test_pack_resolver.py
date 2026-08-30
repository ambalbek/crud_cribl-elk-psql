"""Tests for the pack resolver — resolution, fallback, deprecation, and version pinning."""
from __future__ import annotations

import uuid

import pytest

from app.extensions import db
from app.models import OnboardingRequest, PackRegistry, RequestStatus
from app.services.pack_resolver import resolve_pack


# ── Helpers ─────────────────────────────────────────────────────────────────

def _seed_registry(db_session) -> None:
    """Seed the pack_registry with test data."""
    entries = [
        PackRegistry(
            id=uuid.uuid4(),
            data_type="other",
            pack_id="passthru",
            pack_version="1.0.0",
            attachment="route",
            status="approved",
        ),
        PackRegistry(
            id=uuid.uuid4(),
            data_type="mulesoft",
            pack_id="mulesoft_pack",
            pack_version="1.0.0",
            attachment="route",
            status="approved",
        ),
        PackRegistry(
            id=uuid.uuid4(),
            data_type="forgerock",
            pack_id="forgerock_pack",
            pack_version="1.0.0",
            attachment="route",
            status="approved",
        ),
        PackRegistry(
            id=uuid.uuid4(),
            data_type="oldformat",
            pack_id="oldformat_pack",
            pack_version="0.5.0",
            attachment="route",
            status="deprecated",
        ),
    ]
    for e in entries:
        db_session.add(e)
    db_session.flush()


# ── Tests ───────────────────────────────────────────────────────────────────

class TestPackResolver:

    def test_known_data_type_resolves(self, app, db):
        _seed_registry(db.session)
        ref = resolve_pack("mulesoft")
        assert ref.pack_id == "mulesoft_pack"
        assert ref.pack_version == "1.0.0"
        assert ref.attachment == "route"
        assert ref.data_type == "mulesoft"

    def test_unknown_data_type_falls_back_to_other(self, app, db):
        _seed_registry(db.session)
        ref = resolve_pack("unknownthing")
        assert ref.pack_id == "passthru"
        assert ref.pack_version == "1.0.0"
        assert ref.data_type == "other"

    def test_deprecated_pack_not_returned(self, app, db):
        _seed_registry(db.session)
        ref = resolve_pack("oldformat")
        # Should fall back to 'other' since oldformat is deprecated
        assert ref.pack_id == "passthru"
        assert ref.data_type == "other"

    def test_none_data_type_falls_back(self, app, db):
        _seed_registry(db.session)
        ref = resolve_pack(None)
        assert ref.pack_id == "passthru"
        assert ref.data_type == "other"

    def test_empty_string_falls_back(self, app, db):
        _seed_registry(db.session)
        ref = resolve_pack("")
        assert ref.pack_id == "passthru"
        assert ref.data_type == "other"

    def test_version_pinning_survives_registry_update(self, app, db):
        """A request onboarded at pack_version 1.0.0 still reports 1.0.0
        after the registry row is updated to 2.0.0."""
        _seed_registry(db.session)

        # Resolve and pin at intake time
        ref = resolve_pack("mulesoft")
        assert ref.pack_version == "1.0.0"

        req = OnboardingRequest(
            id=uuid.uuid4(),
            app_name="pinned-app",
            apm_id=f"APM-PIN-{uuid.uuid4().hex[:6]}",
            requestor_name="Tester",
            requestor_email="t@co.com",
            team="platform",
            environment="dev",
            data_type="mulesoft",
            pack_id=ref.pack_id,
            pack_version=ref.pack_version,
            status=RequestStatus.intake_pending,
        )
        db.session.add(req)
        db.session.flush()

        # Now upgrade the registry
        entry = PackRegistry.query.filter_by(data_type="mulesoft").first()
        entry.pack_version = "2.0.0"
        db.session.flush()

        # The request still has the pinned version
        stored = db.session.get(OnboardingRequest, req.id)
        assert stored.pack_version == "1.0.0"
        assert stored.pack_id == "mulesoft_pack"

        # But a NEW resolve gives the updated version
        new_ref = resolve_pack("mulesoft")
        assert new_ref.pack_version == "2.0.0"
