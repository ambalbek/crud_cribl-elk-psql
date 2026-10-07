import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    _raw_db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://etn_user:etn_pass@localhost:5432/etn_onboarding",
    )
    # Force psycopg2 driver — plain "postgresql://" defaults to psycopg (v3)
    # in SQLAlchemy 2.x, which may not be installed.
    if _raw_db_url.startswith("postgresql://"):
        _raw_db_url = _raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    SQLALCHEMY_DATABASE_URI = _raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Auth
    AUTH_BACKEND = os.environ.get("AUTH_BACKEND", "local")
    AUTH_LOCAL_USERS = os.environ.get("AUTH_LOCAL_USERS", "[]")

    # Service URLs — etn_onboarding calls these, never Cribl/ES directly
    CRIBL_SERVICE_URL = os.environ.get("CRIBL_SERVICE_URL", "http://localhost:8001")
    ECE_SERVICE_URL = os.environ.get("ECE_SERVICE_URL", "http://localhost:8002")
    ETN_PORTAL_URL = os.environ.get("ETN_PORTAL_URL", "")
    ETN_PORTAL_API_KEY = os.environ.get("ETN_PORTAL_API_KEY", "")

    # OTel
    OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "etn-onboarding")
    OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
