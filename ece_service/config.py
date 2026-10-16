"""
Pydantic-settings configuration for ece_service.

Reads from /app/config.json (mounted from Secret) with env-var overrides.
Env vars with ECE_ prefix still take precedence when set.
"""
import json
import logging
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("ece-service")

CONFIG_PATH = Path(os.environ.get("APP_CONFIG_PATH", "/app/config.json"))


def _load_config_json() -> dict:
    """Load config.json and return the ece section."""
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text())
            return data.get("ece", {})
    except Exception as exc:
        logger.warning("Failed to read %s: %s", CONFIG_PATH, exc)
    return {}


def _cfg_defaults() -> dict[str, str]:
    """Extract ece-service defaults from config.json."""
    ece = _load_config_json()
    return {
        "ECE_ES_URL": ece.get("es_url", ""),
        "ECE_ES_TOKEN": ece.get("es_token", ""),
        "ECE_ES_USERNAME": ece.get("es_username", ""),
        "ECE_ES_PASSWORD": ece.get("es_password", ""),
        "ECE_ES_URL_PROD": ece.get("es_url_prod", ""),
        "ECE_ES_TOKEN_PROD": ece.get("es_token_prod", ""),
        "ECE_ES_USERNAME_PROD": ece.get("es_username_prod", ""),
        "ECE_ES_PASSWORD_PROD": ece.get("es_password_prod", ""),
        "ECE_KIBANA_URL": ece.get("kibana_url", ""),
        "ECE_KIBANA_TOKEN": ece.get("kibana_token", ""),
        "ECE_KIBANA_USERNAME": ece.get("kibana_username", ""),
        "ECE_KIBANA_PASSWORD": ece.get("kibana_password", ""),
        "ECE_SKIP_SSL": str(ece.get("skip_ssl", False)).lower(),
        "ECE_TIMEOUT": str(ece.get("timeout", 60)),
        "ECE_TEMPLATES_DIR": ece.get("templates_dir", "ops_rm_r_templates_output"),
    }


# Inject config.json values as env-var defaults (real env vars still win)
for _k, _v in _cfg_defaults().items():
    os.environ.setdefault(_k, _v)


class ECESettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ECE_",
        case_sensitive=False,
        extra="ignore",
    )

    # Elasticsearch — nonprod
    es_url: str = Field(default="", description="Elasticsearch nonprod base URL")
    es_token: str = Field(default="", description="ApiKey for ES nonprod (overrides user/pass)")
    es_username: str = Field(default="", description="ES nonprod username")
    es_password: str = Field(default="", description="ES nonprod password")

    # Elasticsearch — prod
    es_url_prod: str = Field(default="", description="Elasticsearch prod base URL")
    es_token_prod: str = Field(default="", description="ApiKey for ES prod")
    es_username_prod: str = Field(default="", description="ES prod username")
    es_password_prod: str = Field(default="", description="ES prod password")

    # Kibana
    kibana_url: str = Field(default="", description="Kibana base URL")
    kibana_token: str = Field(default="", description="ApiKey for Kibana")
    kibana_username: str = Field(default="", description="Kibana username")
    kibana_password: str = Field(default="", description="Kibana password")

    # Shared
    skip_ssl: bool = Field(default=False, description="Disable SSL certificate verification")
    timeout: int = Field(default=60, description="HTTP request timeout in seconds")
    templates_dir: str = Field(
        default="ops_rm_r_templates_output",
        description="Output directory for generated ELK role/role-mapping templates",
    )
    log_level: str = Field(default="INFO", description="Logging level")


settings = ECESettings()
