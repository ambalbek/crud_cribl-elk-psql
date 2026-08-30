"""
Packs router — CRUD for Cribl Stream packs on a worker group.

Endpoints:
  GET    /api/v1/m/{worker_group}/packs          — list installed packs
  GET    /api/v1/m/{worker_group}/packs/{id}     — get one pack
  POST   /api/v1/m/{worker_group}/packs          — install a pack (from URL, Git, or upload)
  PATCH  /api/v1/m/{worker_group}/packs/{id}     — upgrade a pack
  DELETE /api/v1/m/{worker_group}/packs/{id}     — remove a pack
"""
from typing import Any

from fastapi import APIRouter, Body, Depends

from ..deps import CriblClient, get_cribl_client

router = APIRouter(prefix="/api/v1/m/{worker_group}/packs")


@router.get("")
def list_packs(
    worker_group: str,
    client: CriblClient = Depends(get_cribl_client),
) -> list[dict]:
    """List all installed packs for the worker group."""
    return client.list_packs(worker_group)


@router.get("/{pack_id}")
def get_pack(
    worker_group: str,
    pack_id: str,
    client: CriblClient = Depends(get_cribl_client),
) -> dict[str, Any]:
    """Fetch a single installed pack by ID."""
    return client.get_pack(worker_group, pack_id)


@router.post("", status_code=201)
def install_pack(
    worker_group: str,
    payload: dict[str, Any] = Body(...),
    client: CriblClient = Depends(get_cribl_client),
) -> dict[str, Any]:
    """Install a pack from a source (URL, Git repo, or inline spec)."""
    return client.install_pack(worker_group, payload)


@router.patch("/{pack_id}")
def upgrade_pack(
    worker_group: str,
    pack_id: str,
    payload: dict[str, Any] = Body(...),
    client: CriblClient = Depends(get_cribl_client),
) -> dict[str, Any]:
    """Upgrade an installed pack."""
    return client.upgrade_pack(worker_group, pack_id, payload)


@router.delete("/{pack_id}")
def remove_pack(
    worker_group: str,
    pack_id: str,
    client: CriblClient = Depends(get_cribl_client),
) -> dict[str, Any]:
    """Remove an installed pack."""
    return client.remove_pack(worker_group, pack_id)
