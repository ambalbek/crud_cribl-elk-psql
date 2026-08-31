import logging

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from app.auth import require_role
from app.extensions import db
from app.models import OnboardingRequest, RequestStatus, AuditLog
from app.services.pack_resolver import resolve_pack
from app.services.state_machine import transition_request, InvalidTransitionError

logger = logging.getLogger(__name__)

intake_bp = Blueprint("intake", __name__, url_prefix="/api/intake")

REQUIRED_FIELDS = {"app_name", "apm_id", "requestor_name", "requestor_email", "team", "environment"}
VALID_ENVIRONMENTS = {"dev", "stage", "prod"}


@intake_bp.route("/", methods=["POST"])
@require_role("requester")
def submit_request():
    """Submit a new onboarding request.

    Expects a JSON body with at minimum: app_name, apm_id, requestor_name,
    requestor_email, team, environment.  Additional fields are stored in
    ``form_data``.
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400

    missing = REQUIRED_FIELDS - set(body.keys())
    if missing:
        return jsonify({"error": f"Missing required fields: {sorted(missing)}"}), 400

    for field in ("app_emails", "log_destinations", "log_types", "entitlement_groups"):
        val = body.get(field)
        if val is not None and not isinstance(val, list):
            return jsonify({"error": f"{field} must be a list"}), 400

    environment = body["environment"]
    if environment not in VALID_ENVIRONMENTS:
        return jsonify({"error": f"Invalid environment '{environment}'. Must be one of {sorted(VALID_ENVIRONMENTS)}"}), 400

    # Check for duplicate APM ID
    existing = OnboardingRequest.query.filter_by(apm_id=body["apm_id"]).first()
    if existing:
        return jsonify({"error": f"An onboarding request with apm_id '{body['apm_id']}' already exists"}), 409

    # All known columns
    known_keys = {
        "app_name", "apm_id", "requestor_name", "requestor_email", "team",
        "environment", "lan_id", "first_name", "last_name", "app_emails",
        "workspace", "worker_group", "region", "data_type",
        "log_destinations", "log_types", "ilm_tier", "entitlement_groups",
    }
    form_data = {k: v for k, v in body.items() if k not in known_keys}

    # Resolve pack from registry and pin at intake time
    pack_ref = resolve_pack(body.get("data_type"))

    onboarding_req = OnboardingRequest(
        app_name=body["app_name"],
        apm_id=body["apm_id"],
        requestor_name=body["requestor_name"],
        requestor_email=body["requestor_email"],
        team=body["team"],
        environment=environment,
        lan_id=body.get("lan_id"),
        first_name=body.get("first_name"),
        last_name=body.get("last_name"),
        app_emails=body.get("app_emails", []),
        workspace=body.get("workspace"),
        worker_group=body.get("worker_group"),
        region=body.get("region"),
        data_type=body.get("data_type"),
        log_destinations=body.get("log_destinations", []),
        log_types=body.get("log_types", []),
        ilm_tier=body.get("ilm_tier", "none"),
        entitlement_groups=body.get("entitlement_groups", []),
        pack_id=pack_ref.pack_id,
        pack_version=pack_ref.pack_version,
        status=RequestStatus.intake_pending,
        form_data=form_data if form_data else {},
    )
    db.session.add(onboarding_req)
    db.session.flush()

    audit_entry = AuditLog(
        request_id=onboarding_req.id,
        stage=RequestStatus.intake_pending,
        action="submit_onboarding_request",
        actor=body["requestor_email"],
        outcome="success",
        metadata_={"source": "intake_form"},
    )
    db.session.add(audit_entry)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": f"An onboarding request with apm_id '{body['apm_id']}' already exists"}), 409

    logger.info("Onboarding request created: apm_id=%s id=%s", body["apm_id"], onboarding_req.id)

    return jsonify({
        "id": str(onboarding_req.id),
        "apm_id": onboarding_req.apm_id,
        "status": onboarding_req.status.value,
        "created_at": onboarding_req.created_at.isoformat(),
    }), 201


@intake_bp.route("/", methods=["GET"])
@require_role("reader")
def list_requests():
    """List and filter the intake queue.

    Query parameters:
      - status: filter by request status
      - team: filter by team name
      - environment: filter by environment (dev/stage/prod)
      - page: page number (default 1)
      - per_page: items per page (default 20, max 100)
    """
    query = OnboardingRequest.query

    status_filter = request.args.get("status")
    if status_filter:
        try:
            status_enum = RequestStatus(status_filter)
        except ValueError:
            return jsonify({"error": f"Invalid status '{status_filter}'"}), 400
        query = query.filter(OnboardingRequest.status == status_enum)

    team_filter = request.args.get("team")
    if team_filter:
        query = query.filter(OnboardingRequest.team == team_filter)

    env_filter = request.args.get("environment")
    if env_filter:
        if env_filter not in VALID_ENVIRONMENTS:
            return jsonify({"error": f"Invalid environment '{env_filter}'"}), 400
        query = query.filter(OnboardingRequest.environment == env_filter)

    query = query.order_by(OnboardingRequest.created_at.desc())

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    items = [
        {
            "id": str(r.id),
            "app_name": r.app_name,
            "apm_id": r.apm_id,
            "lan_id": r.lan_id,
            "first_name": r.first_name,
            "last_name": r.last_name,
            "requestor_name": r.requestor_name,
            "requestor_email": r.requestor_email,
            "team": r.team,
            "app_emails": r.app_emails,
            "environment": r.environment,
            "workspace": r.workspace,
            "worker_group": r.worker_group,
            "region": r.region,
            "data_type": r.data_type,
            "log_destinations": r.log_destinations,
            "log_types": r.log_types,
            "ilm_tier": r.ilm_tier,
            "entitlement_groups": r.entitlement_groups,
            "pack_id": r.pack_id,
            "pack_version": r.pack_version,
            "status": r.status.value,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in pagination.items
    ]

    return jsonify({
        "items": items,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }), 200


@intake_bp.route("/<uuid:request_id>/validate", methods=["POST"])
@require_role("approver")
def validate_intake(request_id):
    """Validate intake form fields and transition the request to intake_validated.

    Accepts an optional JSON body with ``actor`` (defaults to ``"system"``).
    """
    onboarding_req = db.session.get(OnboardingRequest, request_id)
    if not onboarding_req:
        return jsonify({"error": "Request not found"}), 404

    body = request.get_json(silent=True) or {}
    actor = body.get("actor", "system")

    # Validate that core fields are non-empty
    validation_errors = []
    for field in REQUIRED_FIELDS:
        value = getattr(onboarding_req, field, None)
        if not value:
            validation_errors.append(f"Field '{field}' is empty or missing")

    if validation_errors:
        return jsonify({"error": "Validation failed", "details": validation_errors}), 422

    try:
        audit_entry = transition_request(
            onboarding_req,
            RequestStatus.intake_validated,
            actor=actor,
            action="validate_intake",
            metadata={"validated_fields": sorted(REQUIRED_FIELDS)},
        )
        db.session.commit()
    except InvalidTransitionError as exc:
        return jsonify({"error": str(exc)}), 409

    logger.info("Intake validated: request_id=%s actor=%s", request_id, actor)

    return jsonify({
        "id": str(onboarding_req.id),
        "status": onboarding_req.status.value,
        "audit_id": str(audit_entry.id),
    }), 200
