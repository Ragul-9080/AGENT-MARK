"""Catalyst function: webhooks.

Receives provider callbacks (Vobiz call events, SES email events).
Stores the raw payload first, verifies the workspace HMAC token, then routes
to the appropriate handler. No user session required -- providers call back
with workspace_id + token query params.
Entry point for Catalyst: handler(context, request).
"""

from __future__ import annotations

import json
from typing import Any

from shared.core.config import settings
from shared.core.db import session_scope
from shared.core.errors import AppError


def _parse_body(request: Any) -> dict[str, Any]:
    body = request.get("body", "") if isinstance(request, dict) else ""
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def _response(status_code: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": body if isinstance(body, str) else json.dumps(body),
    }


def _error_response(status_code: int, code: str, message: str) -> dict[str, Any]:
    return _response(status_code, {"error": {"type": code, "message": message}})


def handler(context: Any, request: Any) -> dict[str, Any]:
    """Catalyst entry point for the webhooks function."""

    method = (request.get("method") if isinstance(request, dict) else "POST").upper()
    path = request.get("path", "/") if isinstance(request, dict) else "/"
    body = _parse_body(request)
    query = request.get("queryStringParameters") or {}

    with session_scope() as db:
        try:
            provider = path.strip("/").split("/")[-1] if "/" in path else "email"
            workspace_id = query.get("workspace_id")
            token = query.get("token")

            if not workspace_id or not token:
                return _error_response(401, "unauthorized", "Workspace webhook params required.")

            import uuid

            from shared.services.webhooks import verify_workspace_token, store_delivery  # noqa: E402
            from shared.models.workspace import Workspace  # noqa: E402

            verify_workspace_token(uuid.UUID(workspace_id), token)
            workspace = db.get(Workspace, uuid.UUID(workspace_id))
            if workspace is None:
                return _error_response(404, "workspace_not_found", "We could not find that workspace.")

            raw_body = json.dumps(body).encode("utf-8")
            # Build a minimal request-like object for store_delivery
            class _Req:
                headers = {"content-type": "application/json"}

            delivery = store_delivery(
                db,
                workspace=workspace,
                provider=provider,
                request=_Req(),
                raw_body=raw_body,
            )
            return _response(200, {"status": "accepted", "id": str(delivery.id)})

        except AppError as exc:
            return _error_response(exc.status_code, exc.code, exc.message)
        except Exception:  # pragma: no cover - defensive
            return _error_response(500, "internal_error", "Internal server error.")
