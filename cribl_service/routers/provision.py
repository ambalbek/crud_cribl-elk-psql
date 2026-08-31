"""
Provision router — idempotent bulk push of routes + destinations + packs for multiple apps.

Endpoint:
  POST /api/v1/m/{worker_group}/provision

This is the HTTP equivalent of the cribl-pusher.py CLI workflow.
Flask's /cribl/api/run-pusher calls this endpoint when CRIBL_SERVICE_URL is set,
passing the rendered route/destination templates it already loaded from config.json.
"""
import logging
import time
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from ..deps import CriblClient, get_cribl_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/m/{worker_group}")

MAX_RETRIES = 3
RETRY_BACKOFF = [1, 3, 5]  # seconds between retries


def _retry(fn, description: str, max_retries: int = MAX_RETRIES) -> Any:
    """Execute fn() with retry on transient failures."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            return fn()
        except HTTPException:
            raise  # 4xx errors are not retryable
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                logger.warning(
                    "%s failed (attempt %d/%d), retrying in %ds: %s",
                    description, attempt + 1, max_retries, wait, exc,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "%s failed after %d attempts: %s",
                    description, max_retries, exc,
                )
    raise last_exc  # type: ignore[misc]


def _install_pack_if_needed(
    client: CriblClient,
    worker_group: str,
    pack: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any] | None:
    """Install a pack (idempotent). Returns result dict or None."""
    pack_id = (pack.get("pack_id") or "").strip()
    if not pack_id:
        return None

    if dry_run:
        return {"pack_id": pack_id, "status": "dry_run_skipped"}

    # Check if already installed
    try:
        client.get_pack(worker_group, pack_id)
        return {"pack_id": pack_id, "status": "already_installed"}
    except HTTPException as exc:
        if exc.status_code != 404:
            raise  # unexpected error, don't swallow
    except Exception:
        pass  # network error checking existence — proceed to install

    # Install with retry
    install_payload = {
        "id": pack_id,
        "source": pack.get("source", ""),
        "version": pack.get("pack_version", ""),
    }
    result = _retry(
        lambda: client.install_pack(worker_group, install_payload),
        f"install pack {pack_id}",
    )
    if not isinstance(result, dict):
        result = {"raw": str(result)}
    result["status"] = "installed"
    return result


@router.post("/provision")
def provision(
    worker_group: str,
    body: dict[str, Any] = Body(..., example={
        "apps": [{"apmid": "myapp001", "app_name": "My App"}],
        "route_template": {"pipeline": "passthru", "final": False},
        "dest_template":  {"type": "azure_blob", "region": "azn"},
        "dest_prefix":    "azn-blob",
        "routes_table":   "default",
        "dry_run":        True,
        "fallback_pipeline": "main",
        "pack":           {"pack_id": "mulesoft_pack", "pack_version": "1.0.0", "source": "git"},
    }),
    client: CriblClient = Depends(get_cribl_client),
) -> dict[str, Any]:
    """
    Idempotent bulk provision: add a Cribl route + destination (+ optional pack) for each app.

    Body fields:
    - apps            list of {apmid, app_name}  (required)
    - route_template  dict — base route JSON copied per app  (required)
    - dest_template   dict — base destination JSON copied per app  (required)
    - dest_prefix     str  — prefix for route name and destination id  (required)
    - routes_table    str  — Cribl routes table name (default: "default")
    - dry_run         bool — preview only, no writes (default: true)
    - fallback_pipeline str — pipeline to assign if template has none (default: "main")
    - pack            dict — optional pack reference {pack_id, pack_version, source}
                      When present, the pack is installed (if not already) and the
                      route_template pipeline is set to the pack's pipeline.

    Retries up to 3 times on transient failures.
    Existing routes/destinations are skipped (idempotent).
    """
    apps              = body.get("apps", [])
    route_template    = body.get("route_template", {})
    dest_template     = body.get("dest_template", {})
    dest_prefix       = body.get("dest_prefix", "")
    routes_table      = body.get("routes_table", "default")
    dry_run           = bool(body.get("dry_run", True))
    fallback_pipeline = body.get("fallback_pipeline", "main")
    pack              = body.get("pack")

    # If a pack is specified, install it (idempotent) and use it as the pipeline
    pack_result = None
    if pack:
        pack_result = _install_pack_if_needed(client, worker_group, pack, dry_run)
        pack_id = (pack.get("pack_id") or "").strip()
        if pack_id:
            route_template = {**route_template, "pipeline": pack_id}

    # Provision routes + destinations with retry
    result = _retry(
        lambda: client.provision_apps(
            worker_group=worker_group,
            apps=apps,
            route_template=route_template,
            dest_template=dest_template,
            dest_prefix=dest_prefix,
            routes_table=routes_table,
            dry_run=dry_run,
            fallback_pipeline=fallback_pipeline,
        ),
        f"provision {len(apps)} app(s) on {worker_group}",
    )

    if pack_result:
        result["pack"] = pack_result

    return result
