from collections import deque
from datetime import datetime, timezone

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.onboarding_request import OnboardingRequest, RequestStatus


ALLOWED_TRANSITIONS: dict[RequestStatus, list[RequestStatus]] = {
    RequestStatus.intake_pending: [
        RequestStatus.intake_validated,
        RequestStatus.cancelled,
    ],
    RequestStatus.intake_validated: [
        RequestStatus.engagement,
        RequestStatus.cancelled,
    ],
    RequestStatus.engagement: [
        RequestStatus.solutioning,
        RequestStatus.cancelled,
    ],
    RequestStatus.solutioning: [
        RequestStatus.storage_pending,
        RequestStatus.cancelled,
    ],
    # ── Correct delivery order: storage first, then build on it ──
    RequestStatus.storage_pending: [
        RequestStatus.storage_confirmed,
        RequestStatus.delivery_failed,
        RequestStatus.cancelled,
    ],
    RequestStatus.storage_confirmed: [
        RequestStatus.delivery_destination,
        RequestStatus.delivery_failed,
        RequestStatus.cancelled,
    ],
    RequestStatus.delivery_destination: [
        RequestStatus.delivery_pack,
        RequestStatus.delivery_failed,
        RequestStatus.cancelled,
    ],
    RequestStatus.delivery_pack: [
        RequestStatus.delivery_route,
        RequestStatus.delivery_failed,
        RequestStatus.cancelled,
    ],
    RequestStatus.delivery_route: [
        RequestStatus.delivery_collection,
        RequestStatus.delivery_failed,
        RequestStatus.cancelled,
    ],
    RequestStatus.delivery_collection: [
        RequestStatus.delivery_complete,
        RequestStatus.delivery_failed,
        RequestStatus.cancelled,
    ],
    RequestStatus.delivery_complete: [
        RequestStatus.validation,
        RequestStatus.delivery_failed,
        RequestStatus.cancelled,
    ],
    RequestStatus.delivery_failed: [
        RequestStatus.cancelled,
    ],
    RequestStatus.validation: [
        RequestStatus.reverify,
        RequestStatus.cancelled,
    ],
    RequestStatus.reverify: [
        RequestStatus.complete,
        RequestStatus.cancelled,
    ],
    RequestStatus.complete: [
        RequestStatus.cancelled,
    ],
    RequestStatus.cancelled: [],
}


class InvalidTransitionError(Exception):
    """Raised when a status transition is not allowed."""

    def __init__(
        self,
        current: RequestStatus,
        target: RequestStatus,
    ) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Transition from '{current.value}' to '{target.value}' is not allowed"
        )


def transition_request(
    request: OnboardingRequest,
    new_status: RequestStatus,
    actor: str,
    *,
    action: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Validate and execute a status transition on an onboarding request.

    Args:
        request: The onboarding request to transition.
        new_status: The target status.
        actor: Identifier of the user or system performing the transition.
        action: Optional description of the action (defaults to
            ``"transition <old> -> <new>"``).
        metadata: Optional JSON-serialisable dict stored on the audit log.

    Returns:
        The created :class:`AuditLog` entry.

    Raises:
        InvalidTransitionError: If the transition is not permitted.
    """
    current_status = request.status
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])

    if new_status not in allowed:
        raise InvalidTransitionError(current_status, new_status)

    if action is None:
        action = f"transition {current_status.value} -> {new_status.value}"

    request.status = new_status
    request.updated_at = datetime.now(timezone.utc)

    audit_entry = AuditLog(
        request_id=request.id,
        stage=new_status,
        action=action,
        actor=actor,
        outcome="success",
        metadata_=metadata or {},
    )

    db.session.add(audit_entry)

    return audit_entry


# Ordered rank of each status along the happy path. Used to decide whether a
# request is already at/past a target (so a provisioning callback is idempotent)
# and to know whether we should walk forward to it.
_STATUS_ORDER: list[RequestStatus] = [
    RequestStatus.intake_pending,
    RequestStatus.intake_validated,
    RequestStatus.engagement,
    RequestStatus.solutioning,
    RequestStatus.storage_pending,
    RequestStatus.storage_confirmed,
    RequestStatus.delivery_destination,
    RequestStatus.delivery_pack,
    RequestStatus.delivery_route,
    RequestStatus.delivery_collection,
    RequestStatus.delivery_complete,
    RequestStatus.validation,
    RequestStatus.reverify,
    RequestStatus.complete,
]
_STATUS_RANK: dict[RequestStatus, int] = {s: i for i, s in enumerate(_STATUS_ORDER)}


def _shortest_path(start: RequestStatus, target: RequestStatus) -> list[RequestStatus] | None:
    """BFS over ALLOWED_TRANSITIONS for the shortest start→target path.

    Returns the list of intermediate+target statuses to step through (excluding
    ``start``), or ``None`` if ``target`` is unreachable from ``start``. Avoids
    ``cancelled`` unless it is the explicit target, so we never walk a request
    into a terminal cancel on the way somewhere else.
    """
    if start == target:
        return []
    queue: deque[tuple[RequestStatus, list[RequestStatus]]] = deque([(start, [])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        for nxt in ALLOWED_TRANSITIONS.get(node, []):
            if nxt in seen:
                continue
            if nxt == RequestStatus.cancelled and target != RequestStatus.cancelled:
                continue
            new_path = path + [nxt]
            if nxt == target:
                return new_path
            seen.add(nxt)
            queue.append((nxt, new_path))
    return None


class StatusUnreachableError(Exception):
    """Raised when there is no allowed path from the current status to the target."""

    def __init__(self, current: RequestStatus, target: RequestStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"No allowed transition path from '{current.value}' to '{target.value}'"
        )


def advance_to(
    request: OnboardingRequest,
    target: RequestStatus,
    actor: str,
    *,
    action: str | None = None,
    metadata: dict | None = None,
) -> list[AuditLog]:
    """Walk a request forward through every allowed transition up to ``target``.

    Idempotent and safe for a provisioning callback that only knows the desired
    end state (e.g. "delivery is done"):

      * already at/past ``target`` on the happy path  → no-op, returns ``[]``
      * a legal multi-step path exists                → steps through it, one
        audit log per hop, and the CALLER commits once
      * no legal path (e.g. request was cancelled)    → ``StatusUnreachableError``

    This replaces the portal's old single-hop jump straight to
    ``delivery_complete``, which was illegal from any state except
    ``delivery_collection`` and therefore always 409'd — leaving the etn
    Postgres status stuck while ES/portal showed "done".
    """
    current = request.status

    # Already there or further along the main line — nothing to do.
    cur_rank = _STATUS_RANK.get(current)
    tgt_rank = _STATUS_RANK.get(target)
    if cur_rank is not None and tgt_rank is not None and cur_rank >= tgt_rank:
        return []

    path = _shortest_path(current, target)
    if path is None:
        raise StatusUnreachableError(current, target)

    audits: list[AuditLog] = []
    for i, step in enumerate(path):
        step_action = action if (action and step == target) else f"advance_to {step.value}"
        audits.append(
            transition_request(
                request,
                step,
                actor=actor,
                action=step_action,
                metadata=metadata if step == target else None,
            )
        )
    return audits
