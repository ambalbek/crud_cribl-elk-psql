"""HTTP client that delegates ECE operations to ``ece_service``.

``etn_onboarding`` never talks to Elasticsearch directly.  This client calls
the ``ece_service`` FastAPI microservice over HTTP.
"""
from __future__ import annotations

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


class ECEClient:
    """Synchronous REST client that proxies to ``ece_service``."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(_JSON_HEADERS)
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
        self._session.mount("http://", HTTPAdapter(max_retries=retry))
        self._session.mount("https://", HTTPAdapter(max_retries=retry))

    # ── HTTP helpers ─────────────────────────────────────────────────────

    def _get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self._session.get(url, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _put(self, path: str, json: Any = None, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self._session.put(url, json=json, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _delete(self, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self._session.delete(url, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    # ── Roles ────────────────────────────────────────────────────────────

    def create_role(
        self,
        name: str,
        body: dict[str, Any],
        target: str = "nonprod",
    ) -> dict[str, Any]:
        """Create or update an Elasticsearch role via ``ece_service``."""
        logger.info("create_role: name=%s target=%s", name, target)
        return self._put(
            f"/api/v1/roles/{name}",
            json=body,
            params={"target": target},
        )

    def create_role_mapping(
        self,
        name: str,
        body: dict[str, Any],
        target: str = "nonprod",
    ) -> dict[str, Any]:
        """Create or update a role mapping via ``ece_service``."""
        logger.info("create_role_mapping: name=%s target=%s", name, target)
        return self._put(
            f"/api/v1/role-mappings/{name}",
            json=body,
            params={"target": target},
        )

    # ── Indexes ──────────────────────────────────────────────────────────

    def create_index(
        self,
        name: str,
        body: dict[str, Any],
        target: str = "nonprod",
    ) -> dict[str, Any]:
        """Create an index template via ``ece_service``."""
        logger.info("create_index: name=%s target=%s", name, target)
        return self._put(
            f"/api/v1/indexes/{name}",
            json=body,
            params={"target": target},
        )

    # ── Provisioning ─────────────────────────────────────────────────────

    def provision_app(
        self,
        apm_id: str,
        app_name: str,
        environment: str,
    ) -> dict[str, Any]:
        """Provision roles and role-mappings for an app via ``ece_service``."""
        logger.info("provision_app: apm_id=%s env=%s", apm_id, environment)
        return self._put(
            "/api/v1/roles/provision",
            json={
                "apps": [{"apmid": apm_id, "app_name": app_name}],
                "environment": environment,
            },
        )

    # ── Health ───────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        return self._get("/health")
