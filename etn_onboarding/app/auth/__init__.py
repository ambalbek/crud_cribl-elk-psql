"""Authentication and authorisation for the ETN Onboarding API.

Provides:
  - ``AuthUser``       — lightweight identity container stored on ``g``
  - ``require_auth``   — decorator that validates the bearer token
  - ``require_role``   — decorator that enforces role-based access
  - ``init_auth``      — factory that wires the configured verifier
"""
from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

from flask import current_app, g, jsonify, request

if TYPE_CHECKING:
    from flask import Flask


# ── Role hierarchy ──────────────────────────────────────────────────────────

ROLE_INCLUDES: dict[str, set[str]] = {
    "platform_admin": {"platform_admin", "approver", "requester", "reader"},
    "approver": {"approver", "requester", "reader"},
    "requester": {"requester", "reader"},
    "reader": {"reader"},
}


# ── Identity ────────────────────────────────────────────────────────────────

class AuthUser:
    """Authenticated user identity attached to ``flask.g``."""

    __slots__ = ("username", "roles")

    def __init__(self, username: str, roles: list[str]) -> None:
        self.username = username
        self.roles = roles

    def has_role(self, target: str) -> bool:
        """Return *True* if any of the user's roles include *target*."""
        for role in self.roles:
            if target in ROLE_INCLUDES.get(role, set()):
                return True
        return False


def get_current_user() -> AuthUser | None:
    """Return the authenticated user, or ``None`` outside a request."""
    return getattr(g, "auth_user", None)


# ── Verifier protocol ──────────────────────────────────────────────────────

@runtime_checkable
class AuthVerifier(Protocol):
    """Interface that every auth backend must implement."""

    def verify(self, token: str) -> AuthUser | None:
        """Return an ``AuthUser`` for a valid *token*, or ``None``."""
        ...


# ── Decorators ──────────────────────────────────────────────────────────────

def require_auth(fn: Callable) -> Callable:
    """Reject requests that lack a valid ``Authorization: Bearer …`` token."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verifier: AuthVerifier | None = current_app.config.get("AUTH_VERIFIER")
        if verifier is None:
            return jsonify({"error": "Authentication not configured"}), 500

        token = _extract_bearer_token()
        if not token:
            return jsonify({"error": "Missing or malformed Authorization header"}), 401

        user = verifier.verify(token)
        if user is None:
            return jsonify({"error": "Invalid or expired token"}), 401

        g.auth_user = user
        return fn(*args, **kwargs)

    return wrapper


def require_role(*roles: str) -> Callable:
    """Reject requests from users lacking at least one of *roles*.

    Implicitly calls ``require_auth`` first.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verifier: AuthVerifier | None = current_app.config.get("AUTH_VERIFIER")
            if verifier is None:
                return jsonify({"error": "Authentication not configured"}), 500

            token = _extract_bearer_token()
            if not token:
                return jsonify({"error": "Missing or malformed Authorization header"}), 401

            user = verifier.verify(token)
            if user is None:
                return jsonify({"error": "Invalid or expired token"}), 401

            g.auth_user = user

            if not any(user.has_role(r) for r in roles):
                return jsonify({
                    "error": "Insufficient permissions",
                    "required_roles": list(roles),
                }), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator


# ── Init helper ─────────────────────────────────────────────────────────────

def init_auth(flask_app: Flask) -> None:
    """Wire the auth verifier determined by ``AUTH_BACKEND``."""
    backend = flask_app.config.get("AUTH_BACKEND", "local")

    if backend == "local":
        from app.auth.local import LocalVerifier

        flask_app.config["AUTH_VERIFIER"] = LocalVerifier.from_config(flask_app)
    elif backend == "oidc":
        from app.auth.oidc import OIDCVerifier

        flask_app.config["AUTH_VERIFIER"] = OIDCVerifier.from_config(flask_app)
    else:
        raise ValueError(f"Unknown AUTH_BACKEND: {backend!r}")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _extract_bearer_token() -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return None
