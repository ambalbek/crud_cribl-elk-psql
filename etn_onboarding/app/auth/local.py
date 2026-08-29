"""Local (token-based) authentication backend.

Users are defined via the ``AUTH_LOCAL_USERS`` Flask config key, which holds a
JSON-encoded list of user objects::

    [
      {"username": "admin",  "token": "secret-1", "roles": ["platform_admin"]},
      {"username": "viewer", "token": "secret-2", "roles": ["reader"]}
    ]

Set the environment variable ``AUTH_LOCAL_USERS`` to populate this automatically
(see ``config.py``).
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from app.auth import AuthUser

if TYPE_CHECKING:
    from flask import Flask

logger = logging.getLogger(__name__)


class LocalVerifier:
    """Look up bearer tokens in a static in-memory dict."""

    def __init__(self, users_by_token: dict[str, AuthUser]) -> None:
        self._users_by_token = users_by_token

    # ── Factory ─────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, flask_app: Flask) -> LocalVerifier:
        raw = flask_app.config.get("AUTH_LOCAL_USERS", "[]")
        if isinstance(raw, str):
            entries = json.loads(raw)
        else:
            entries = raw

        users_by_token: dict[str, AuthUser] = {}
        for entry in entries:
            token = entry["token"]
            user = AuthUser(
                username=entry["username"],
                roles=entry.get("roles", ["reader"]),
            )
            users_by_token[token] = user

        logger.info("LocalVerifier loaded %d user(s)", len(users_by_token))
        return cls(users_by_token)

    # ── AuthVerifier protocol ───────────────────────────────────────────

    def verify(self, token: str) -> AuthUser | None:
        return self._users_by_token.get(token)
