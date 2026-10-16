"""
Settings for ece_service.

Reads from /app/config.json (ece section) with env-var overrides.
deps.py and main.py import from here for backwards compatibility.
"""
from .config import settings as _s

# ── Elasticsearch — nonprod ──────────────────────────────────────────────────
ECE_ES_URL: str      = _s.es_url.rstrip("/")
ECE_ES_TOKEN: str    = _s.es_token
ECE_ES_USERNAME: str = _s.es_username
ECE_ES_PASSWORD: str = _s.es_password

# ── Elasticsearch — prod ─────────────────────────────────────────────────────
ECE_ES_URL_PROD: str      = _s.es_url_prod.rstrip("/") if _s.es_url_prod else ""
ECE_ES_TOKEN_PROD: str    = _s.es_token_prod
ECE_ES_USERNAME_PROD: str = _s.es_username_prod
ECE_ES_PASSWORD_PROD: str = _s.es_password_prod

# ── Kibana ────────────────────────────────────────────────────────────────────
ECE_KIBANA_URL: str      = _s.kibana_url.rstrip("/") if _s.kibana_url else ""
ECE_KIBANA_TOKEN: str    = _s.kibana_token
ECE_KIBANA_USERNAME: str = _s.kibana_username
ECE_KIBANA_PASSWORD: str = _s.kibana_password

# ── Shared ────────────────────────────────────────────────────────────────────
ECE_SKIP_SSL: bool = _s.skip_ssl
LOG_LEVEL: str     = _s.log_level.upper()

# Output directory for generated ELK templates (same as role_rm.py default)
TEMPLATES_OUTPUT_DIR: str = _s.templates_dir
