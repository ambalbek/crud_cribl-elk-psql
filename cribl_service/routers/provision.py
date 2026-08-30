"""
Provision router — idempotent bulk push of routes + destinations + packs for multiple apps.

Endpoint:
  POST /api/v1/m/{worker_group}/provision

This is the HTTP equivalent of the cribl-pusher.py CLI workflow.
Flask's /cribl/api/run-pusher calls this endpoint when CRIBL_SERVICE_URL is set,
passing the rendered route/destination templates it already loaded from config.json.
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from ..deps import CriblClient, get_cribl_client

router = APIRouter(prefix="/api/v1/m/{worker_group}")


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

    Existing routes/destinations are skipped (idempotent).
    All new routes are inserted in a single PATCH for atomicity.
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
        pack_id = pack.get("pack_id", "")
        if pack_id and not dry_run:
            try:
                existing = client.get_pack(worker_group, pack_id)
                pack_result = {"pack_id": pack_id, "status": "already_installed"}
            except Exception:
                install_payload = {
                    "id": pack_id,
                    "source": pack.get("source", ""),
                    "version": pack.get("pack_version", ""),
                }
                pack_result = client.install_pack(worker_group, install_payload)
                pack_result["status"] = "installed"

            # Set the route template pipeline to the pack
            route_template = {**route_template, "pipeline": pack_id}
        elif pack_id and dry_run:
            pack_result = {"pack_id": pack_id, "status": "dry_run_skipped"}
            route_template = {**route_template, "pipeline": pack_id}

    result = client.provision_apps(
        worker_group=worker_group,
        apps=apps,
        route_template=route_template,
        dest_template=dest_template,
        dest_prefix=dest_prefix,
        routes_table=routes_table,
        dry_run=dry_run,
        fallback_pipeline=fallback_pipeline,
    )

    if pack_result:
        result["pack"] = pack_result

    return result
