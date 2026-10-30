"""
Cribl service configuration.

Reads from /app/config.json (mounted from Secret) with env-var overrides.
Env vars with CRIBL_ prefix still take precedence when set.
"""
import json
import logging
import os
import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Make project root importable for config_resolver
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config_resolver import resolve_config

logger = logging.getLogger("cribl-service")

CONFIG_PATH = Path(os.environ.get("APP_CONFIG_PATH", "/app/config.json"))


def _load_config_json() -> dict:
    """Load config.json, resolve globals, return root."""
    try:
        if CONFIG_PATH.exists():
            return resolve_config(json.loads(CONFIG_PATH.read_text()))
    except Exception as exc:
        logger.warning("Failed to read %s: %s", CONFIG_PATH, exc)
    return {}


def _cfg_defaults() -> dict[str, str]:
    """Extract cribl-service defaults from config.json."""
    cfg = _load_config_json()
    creds = cfg.get("credentials", {})
    return {
        "CRIBL_BASE_URL": cfg.get("base_url", [""])[0] if isinstance(cfg.get("base_url"), list) else cfg.get("base_url", ""),
        "CRIBL_TOKEN": creds.get("token", ""),
        "CRIBL_USERNAME": creds.get("username", ""),
        "CRIBL_PASSWORD": creds.get("password", ""),
        "CRIBL_SKIP_SSL": str(cfg.get("skip_ssl", False)).lower(),
        "CRIBL_SNAPSHOT_DIR": cfg.get("snapshot_dir", "cribl_snapshots"),
        "CRIBL_MIN_EXISTING_ROUTES": str(cfg.get("min_existing_total_routes", 1)),
        "CRIBL_LOG_LEVEL": cfg.get("log_level", "INFO"),
    }


# Inject config.json values as env-var defaults (real env vars still win)
for _k, _v in _cfg_defaults().items():
    os.environ.setdefault(_k, _v)


class CriblSettings(BaseSettings):
    """Typed settings for cribl_service — sourced from config.json + env vars."""

    model_config = SettingsConfigDict(
        env_prefix="CRIBL_",
        case_sensitive=False,
        extra="ignore",
    )

    base_url: str = Field(default="", description="Cribl Stream leader base URL (e.g. https://cribl.example.com:9000)")
    token: str = Field(default="", description="Cribl bearer token — preferred over username/password")
    username: str = Field(default="", description="Cribl username for password-based auth")
    password: str = Field(default="", description="Cribl password for password-based auth")
    skip_ssl: bool = Field(default=False, description="Disable TLS certificate verification")
    timeout: int = Field(default=30, description="HTTP request timeout in seconds")
    default_workspace: str = Field(default="default", description="Default workspace name when none is specified")
    default_routes_table: str = Field(default="default", description="Default route table name")
    min_existing_routes: int = Field(default=1, description="Safety check: refuse to PATCH if fewer routes than this exist")
    snapshot_dir: str = Field(default="cribl_snapshots", description="Directory for pre-patch route snapshots")
    log_level: str = Field(default="INFO", description="Logging verbosity: DEBUG | INFO | WARNING | ERROR")


settings = CriblSettings()

