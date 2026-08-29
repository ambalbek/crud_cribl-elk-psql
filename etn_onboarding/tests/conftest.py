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


@pytest.fixture(scope="session")
def app() -> Flask:
    """Create the Flask application with a test database."""
    flask_app = create_app(config_class=TestConfig)
    with flask_app.app_context():
        _db.create_all()
    yield flask_app
    with flask_app.app_context():
        _db.drop_all()


@pytest.fixture()
def db(app: Flask):
    """Provide a clean database for each test via transaction rollback."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()

        options = {"bind": connection}
        session = _db.create_scoped_session(options=options)
        old_session = _db.session
        _db.session = session

        yield _db

        transaction.rollback()
        connection.close()
        session.remove()
        _db.session = old_session


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
