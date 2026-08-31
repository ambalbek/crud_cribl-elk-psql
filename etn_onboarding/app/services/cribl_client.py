"""HTTP client that delegates Cribl operations to ``cribl_service``.

``etn_onboarding`` never talks to Cribl directly.  This client calls the
``cribl_service`` FastAPI microservice over HTTP.
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


class CriblClient:
    """Synchronous REST client that proxies to ``cribl_service``."""

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

    def _post(self, path: str, json: Any = None, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self._session.post(url, json=json, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _patch(self, path: str, json: Any = None, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self._session.patch(url, json=json, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _delete(self, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self._session.delete(url, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    # ── Edge operations ──────────────────────────────────────────────────

    def configure_edge_agent(
        self,
        app_name: str,
        apm_id: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Configure a Cribl Edge fleet via ``cribl_service``."""
        payload = {"id": apm_id, "name": app_name, **(config or {})}
        logger.info("configure_edge_agent: apm_id=%s", apm_id)
        return self._post("/cribl/edge/fleets", json=payload)

    # ── Stream route operations ──────────────────────────────────────────

    def create_route(
        self,
        worker_group: str,
        table: str,
        route_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a route via ``cribl_service``."""
        logger.info("create_route: worker_group=%s table=%s", worker_group, table)
        return self._post(
            "/cribl/stream/routes",
            json=route_payload,
            params={"worker_group": worker_group, "routes_table": table},
        )

    # ── Stream destination operations ────────────────────────────────────

    def create_destination(
        self,
        worker_group: str,
        dest_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a destination via ``cribl_service``."""
        logger.info("create_destination: worker_group=%s", worker_group)
        return self._post(
            "/cribl/stream/destinations",
            json=dest_payload,
            params={"worker_group": worker_group},
        )

    # ── Provision (bulk) ─────────────────────────────────────────────────

    def provision(
        self,
        worker_group: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Bulk provision routes and destinations via ``cribl_service``."""
        logger.info("provision: worker_group=%s apps=%d", worker_group, len(body.get("apps", [])))
        return self._post(f"/api/v1/m/{worker_group}/provision", json=body)

    # ── Health ───────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        return self._get("/health")
