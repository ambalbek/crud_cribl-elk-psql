"""Shared pytest fixtures for the ETN Onboarding test suite.

Requires a running PostgreSQL instance.  Set ``TEST_DATABASE_URL`` to override
the default connection string.
"""
from __future__ import annotations

import json
import os
import uuid

import pytest
from flask import Flask

from app import create_app
from app.extensions import db as _db
from app.models import OnboardingRequest, RequestStatus

# ── Test users ──────────────────────────────────────────────────────────────

TEST_USERS = [
    {"username": "admin", "token": "test-admin-token", "roles": ["platform_admin"]},
    {"username": "approver", "token": "test-approver-token", "roles": ["approver"]},
    {"username": "requester", "token": "test-requester-token", "roles": ["requester"]},
    {"username": "reader", "token": "test-reader-token", "roles": ["reader"]},
]


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://etn_user:etn_pass@localhost:5432/etn_onboarding_test",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret"

    AUTH_BACKEND = "local"
    AUTH_LOCAL_USERS = json.dumps(TEST_USERS)

    CRIBL_SERVICE_URL = "http://localhost:8001"
    ECE_SERVICE_URL = "http://localhost:8002"
    ETN_PORTAL_URL = "http://localhost:8080"
    ETN_PORTAL_API_KEY = "test-key"


def _create_enums(db_session) -> None:
    """Create PostgreSQL enum types before db.create_all (models use create_type=False)."""
    from sqlalchemy import text
    enums = [
        "DO $$ BEGIN CREATE TYPE environment_enum AS ENUM ('dev','stage','prod'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
        (
            "DO $$ BEGIN CREATE TYPE request_status_enum AS ENUM ("
            "'intake_pending','intake_validated','engagement','solutioning',"
            "'storage_pending','storage_confirmed',"
            "'delivery_destination','delivery_pack','delivery_route',"
            "'delivery_collection','delivery_routing','delivery_storage',"
            "'delivery_complete','delivery_failed','validation','reverify','complete','cancelled'"
            "); EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        ),
        "DO $$ BEGIN CREATE TYPE job_type_enum AS ENUM ('cribl_edge','etn_portal','harness_blob'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
        "DO $$ BEGIN CREATE TYPE job_status_enum AS ENUM ('pending','running','success','failed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
    ]
    for stmt in enums:
        db_session.execute(text(stmt))
    db_session.commit()


@pytest.fixture(scope="session")
def app() -> Flask:
    """Create the Flask application with a test database."""
    flask_app = create_app(config_class=TestConfig)
    with flask_app.app_context():
        _create_enums(_db.session)
        _db.create_all()
    yield flask_app
    with flask_app.app_context():
        _db.drop_all()


@pytest.fixture()
def db(app: Flask):
    """Provide a clean database for each test via nested transaction rollback."""
    with app.app_context():
        _db.session.begin_nested()
        yield _db
        _db.session.rollback()
        _db.session.remove()


@pytest.fixture()
def client(app: Flask, db):
    """Flask test client with a clean database."""
    return app.test_client()


# ── Auth header helpers ─────────────────────────────────────────────────────

@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-admin-token", "Content-Type": "application/json"}


@pytest.fixture()
def approver_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-approver-token", "Content-Type": "application/json"}


@pytest.fixture()
def requester_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-requester-token", "Content-Type": "application/json"}


@pytest.fixture()
def reader_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-reader-token", "Content-Type": "application/json"}


# ── Sample data ─────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_request(db) -> OnboardingRequest:
    """Insert a minimal onboarding request in ``intake_pending``."""
    req = OnboardingRequest(
        id=uuid.uuid4(),
        app_name="test-app",
        apm_id=f"APM-{uuid.uuid4().hex[:8].upper()}",
        requestor_name="Test User",
        requestor_email="test@example.com",
        team="platform",
        environment="dev",
        status=RequestStatus.intake_pending,
    )
    db.session.add(req)
    db.session.flush()
    return req
