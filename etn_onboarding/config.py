"""
ETN onboarding service configuration.

Reads from /app/config.json (mounted from Secret) with env-var overrides.
"""
import json
import logging
import os
import sys
from pathlib import Path

# Make config_resolver importable — it lives at /app/config_resolver.py
# alongside the etn_onboarding/ package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from config_resolver import resolve_config
except ImportError:
    def resolve_config(x):
        return x

logger = logging.getLogger("etn-onboarding")

CONFIG_PATH = Path(os.environ.get("APP_CONFIG_PATH", str(Path(__file__).resolve().parent.parent / "config.json")))


def _load_config_json() -> dict:
    """Load the etn_onboarding section from config.json with globals resolved."""
    try:
        if CONFIG_PATH.exists():
            data = resolve_config(json.loads(CONFIG_PATH.read_text()))
            return data.get("etn_onboarding", {})
    except Exception as exc:
        logger.warning("Failed to read %s: %s", CONFIG_PATH, exc)
    return {}


_etn = _load_config_json()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", _etn.get("secret_key", "dev-secret-change-me"))
    _raw_db_url = os.environ.get(
        "DATABASE_URL",
        _etn.get("database_url", "postgresql://etn_user:etn_pass@localhost:5432/etn_onboarding"),
    )
    # Force psycopg2 driver — plain "postgresql://" defaults to psycopg (v3)
    # in SQLAlchemy 2.x, which may not be installed.
    if _raw_db_url.startswith("postgresql://"):
        _raw_db_url = _raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    SQLALCHEMY_DATABASE_URI = _raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Auth
    AUTH_BACKEND = os.environ.get("AUTH_BACKEND", _etn.get("auth_backend", "local"))
    _auth_local_users_default = json.dumps(_etn.get("auth_local_users", []))
    AUTH_LOCAL_USERS = os.environ.get("AUTH_LOCAL_USERS", _auth_local_users_default)

    # Service URLs — etn_onboarding calls these, never Cribl/ES directly
    CRIBL_SERVICE_URL = os.environ.get(
        "CRIBL_SERVICE_URL", _etn.get("cribl_service_url", "http://localhost:8001")
    )
    ECE_SERVICE_URL = os.environ.get(
        "ECE_SERVICE_URL", _etn.get("ece_service_url", "http://localhost:8002")
    )
    ETN_PORTAL_URL = os.environ.get("ETN_PORTAL_URL", _etn.get("etn_portal_url", ""))
    ETN_PORTAL_API_KEY = os.environ.get("ETN_PORTAL_API_KEY", _etn.get("etn_portal_api_key", ""))

    # OTel
    OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "etn-onboarding")
    OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
