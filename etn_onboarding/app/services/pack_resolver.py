"""Pack resolver — looks up an approved pack for a data type.

The resolver returns a ``PackRef`` with pack_id, pack_version, and attachment.
The values are pinned onto the onboarding request at intake time so that a
later registry update does not silently change an already-onboarded app.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.models.pack_registry import PackRegistry

logger = logging.getLogger(__name__)

FALLBACK_DATA_TYPE = "other"


@dataclass(frozen=True)
class PackRef:
    pack_id: str
    pack_version: str
    attachment: str
    data_type: str


def resolve_pack(data_type: str | None) -> PackRef:
    """Look up an approved pack. Falls back to 'other'. Never raises."""
    lookup = (data_type or "").strip().lower() or FALLBACK_DATA_TYPE

    entry = PackRegistry.query.filter_by(
        data_type=lookup,
        status="approved",
    ).first()

    if entry is None and lookup != FALLBACK_DATA_TYPE:
        logger.info("No approved pack for data_type=%r, falling back to '%s'", lookup, FALLBACK_DATA_TYPE)
        entry = PackRegistry.query.filter_by(
            data_type=FALLBACK_DATA_TYPE,
            status="approved",
        ).first()

    if entry is None:
        logger.warning("No approved pack found for data_type=%r and no fallback", lookup)
        return PackRef(
            pack_id="passthru",
            pack_version="0.0.0",
            attachment="route",
            data_type=lookup,
        )

    return PackRef(
        pack_id=entry.pack_id,
        pack_version=entry.pack_version,
        attachment=entry.attachment,
        data_type=entry.data_type,
    )
