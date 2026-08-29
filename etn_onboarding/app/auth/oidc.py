"""OIDC authentication backend (seam — not yet implemented).

This module exists so that the auth system has a clean extension point for
token validation via an OpenID Connect provider.  Wire it by setting
``AUTH_BACKEND=oidc`` in the environment.

Required config keys (to be added when implementing):
  - ``OIDC_ISSUER_URL``
  - ``OIDC_AUDIENCE``
  - ``OIDC_ROLES_CLAIM`` (default ``roles``)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.auth import AuthUser

if TYPE_CHECKING:
    from flask import Flask


class OIDCVerifier:
    """Validate JWTs issued by an OIDC provider."""

    @classmethod
    def from_config(cls, flask_app: "Flask") -> "OIDCVerifier":
        raise NotImplementedError(
            "OIDC backend is not yet implemented. "
            "Set AUTH_BACKEND=local or provide a concrete OIDCVerifier."
        )

    def verify(self, token: str) -> AuthUser | None:
        raise NotImplementedError
