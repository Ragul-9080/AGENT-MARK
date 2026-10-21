"""Catalyst function: auth.

Handles user registration, login, token refresh, and /auth/me.
Entry point for Catalyst: handler(context, request).
"""

from __future__ import annotations

import json
from typing import Any

from shared.core.config import settings
from shared.core.db import session_scope
from shared.core.errors import AppError

# Deferred imports keep cold-start time low.
from app.services.auth import (  # noqa: E402
    authenticate_user,
    create_user_and_workspace,
    create_token_pair,
    decode_token,
)
from app.schemas.auth import (  # noqa: E402
    LoginRequest,
    RegisterRequest,
)


def _parse_body(request: Any) -> dict[str, Any]:
    body = request.get("body", "") if isinstance(request, dict) else ""
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
        },
        "body": json.dumps(body),
    }


def _error_response(status_code: int, code: str, message: str) -> dict[str, Any]:
    return _response(
        status_code,
        {"error": {"type": code, "message": message}},
    )


def handler(context: Any, request: Any) -> dict[str, Any]:
    """Catalyst entry point for the auth function."""

    method = (request.get("method") if isinstance(request, dict) else "GET").upper()
    path = request.get("path", "/") if isinstance(request, dict) else "/"
    body = _parse_body(request)

    with session_scope() as db:
        try:
            # POST /auth/register
            if method == "POST" and path == "/auth/register":
                data = RegisterRequest(**body)
                user, workspace = create_user_and_workspace(
                    db,
                    name=data.name,
                    email=data.email,
                    password=data.password,
                    workspace_name=data.workspace_name,
                )
                tokens = create_token_pair(user.id, workspace.id, user.role)
                return _response(201, {"user": user.id, "workspace": workspace.id, "tokens": tokens})

            # POST /auth/login
            if method == "POST" and path == "/auth/login":
                data = LoginRequest(**body)
                user = authenticate_user(db, data.email, data.password)
                tokens = create_token_pair(user.id, user.workspace_id, user.role)
                return _response(200, {"tokens": tokens})

            # GET /auth/me
            if method == "GET" and path == "/auth/me":
                auth_header = (request.get("headers") or {}).get("authorization", "")
                if not auth_header.lower().startswith("bearer "):
                    return _error_response(401, "unauthorized", "Please sign in to continue.")
                token = auth_header.split(" ", 1)[1]
                payload = decode_token(token, "access")
                user_id = payload["sub"]
                workspace_id = payload["ws"]
                user = db.get(__import__("app.models.user", fromlist=["User"]).User, user_id)
                if user is None or str(user.workspace_id) != str(workspace_id):
                    return _error_response(401, "invalid_token", "Your session is not valid.")
                return _response(200, {"user_id": str(user.id), "workspace_id": str(user.workspace_id), "role": user.role})

            return _error_response(404, "not_found", "Auth endpoint not found.")

        except AppError as exc:
            return _error_response(exc.status_code, exc.code, exc.message)
        except Exception:  # pragma: no cover - defensive
            return _error_response(500, "internal_error", "Internal server error.")
