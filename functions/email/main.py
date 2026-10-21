"""Catalyst function: email.

Send emails (console provider by default; flip to SES with env vars),
list messages, and handle provider webhooks (SES bounce/delivery/etc).
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
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
        },
        "body": body if isinstance(body, str) else json.dumps(body),
    }


def _error_response(status_code: int, code: str, message: str) -> dict[str, Any]:
    return _response(status_code, {"error": {"type": code, "message": message}})


def _current_user(request: Any) -> dict[str, Any]:
    headers = request.get("headers") or {}
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise AppError(401, "unauthorized", "Please sign in to continue.")
    import jwt

    token = auth.split(" ", 1)[1]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return {"user_id": payload["sub"], "workspace_id": payload["ws"]}


def handler(context: Any, request: Any) -> dict[str, Any]:
    """Catalyst entry point for the email function."""

    method = (request.get("method") if isinstance(request, dict) else "GET").upper()
    path = request.get("path", "/") if isinstance(request, dict) else "/"
    body = _parse_body(request)
    query = request.get("queryStringParameters") or {}

    with session_scope() as db:
        try:
            # POST /email/send
            if method == "POST" and path == "/email/send":
                user = _current_user(request)
                from shared.services.email import send_email  # noqa: E402
                from shared.schemas.email import EmailSend  # noqa: E402

                data = EmailSend(**body)
                message = send_email(
                    db,
                    workspace_id=user["workspace_id"],
                    data=data,
                    actor_id=user["user_id"],
                )
                return _response(202, {
                    "message_id": str(message.id),
                    "status": message.status.value if hasattr(message.status, "value") else str(message.status),
                    "provider_message_id": message.provider_message_id,
                })

            # GET /email/messages
            if method == "GET" and path == "/email/messages":
                user = _current_user(request)
                from shared.services.email import list_email_messages  # noqa: E402

                items, _total = list_email_messages(
                    db,
                    workspace_id=user["workspace_id"],
                    limit=int(query.get("limit", 50)),
                    offset=int(query.get("offset", 0)),
                )
                return _response(200, [i.__dict__ for i in items])

            # POST /email/webhooks (provider callback, no user session)
            if method == "POST" and path == "/email/webhooks":
                from shared.services.webhooks import verify_workspace_token  # noqa: E402
                from shared.services.email import record_webhook_event  # noqa: E402
                from shared.schemas.email import EmailWebhookEvent  # noqa: E402

                workspace_id = query.get("workspace_id")
                token = query.get("token")
                if not workspace_id or not token:
                    return _error_response(401, "unauthorized", "Workspace webhook params required.")
                verify_workspace_token(__import__("uuid", fromlist=["uuid"]).uuid.UUID(workspace_id), token)

                event = EmailWebhookEvent(**body)
                record_webhook_event(db, workspace_id=__import__("uuid", fromlist=["uuid"]).uuid.UUID(workspace_id), event=event)
                return _response(204, {})

            return _error_response(404, "not_found", "Email endpoint not found.")

        except AppError as exc:
            return _error_response(exc.status_code, exc.code, exc.message)
        except Exception:  # pragma: no cover - defensive
            return _error_response(500, "internal_error", "Internal server error.")
