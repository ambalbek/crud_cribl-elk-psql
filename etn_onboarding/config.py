import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://etn_user:etn_pass@localhost:5432/etn_onboarding",
    )
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
