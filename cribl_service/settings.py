"""
Settings for cribl_service.

Reads from /app/config.json via config.py with env-var overrides.
"""
from .config import settings as _s

# Cribl Stream connection
CRIBL_BASE_URL: str = _s.base_url.rstrip("/") if _s.base_url else ""
CRIBL_TOKEN: str = _s.token
CRIBL_USERNAME: str = _s.username
CRIBL_PASSWORD: str = _s.password
CRIBL_SKIP_SSL: bool = _s.skip_ssl

# HTTP behaviour
CRIBL_TIMEOUT: int = _s.timeout

# Defaults for route/workspace operations
CRIBL_DEFAULT_WORKSPACE: str = _s.default_workspace
CRIBL_DEFAULT_ROUTES_TABLE: str = _s.default_routes_table
CRIBL_MIN_EXISTING_ROUTES: int = _s.min_existing_routes

# Snapshot storage
CRIBL_SNAPSHOT_DIR: str = _s.snapshot_dir

# Logging
LOG_LEVEL: str = _s.log_level.upper()
