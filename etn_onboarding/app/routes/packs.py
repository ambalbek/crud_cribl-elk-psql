import logging

from flask import Blueprint, jsonify
from sqlalchemy import func

from app.auth import require_role
from app.extensions import db
from app.models import OnboardingRequest

logger = logging.getLogger(__name__)

packs_bp = Blueprint("packs", __name__, url_prefix="/api/packs")


@packs_bp.route("/coverage", methods=["GET"])
@require_role("reader")
def coverage():
    """Count onboarding requests grouped by data_type.

    Highlights the 'other' bucket so we know which pack to build next.
    """
    rows = (
        db.session.query(
            func.coalesce(OnboardingRequest.data_type, "other").label("data_type"),
            func.count().label("count"),
        )
        .group_by(func.coalesce(OnboardingRequest.data_type, "other"))
        .order_by(func.count().desc())
        .all()
    )

    items = [
        {
            "data_type": row.data_type,
            "count": row.count,
            "is_fallback": row.data_type == "other",
        }
        for row in rows
    ]

    return jsonify({"coverage": items}), 200
