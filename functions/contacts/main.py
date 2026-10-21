"""Catalyst function: contacts.

CRUD, search, filters, CSV import preview/commit, consent controls, eligibility.
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
    """Extract workspace_id and user_id from the Bearer token."""
    headers = request.get("headers") or {}
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise AppError(401, "unauthorized", "Please sign in to continue.")
    import jwt

    token = auth.split(" ", 1)[1]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return {"user_id": payload["sub"], "workspace_id": payload["ws"]}


def handler(context: Any, request: Any) -> dict[str, Any]:
    """Catalyst entry point for the contacts function."""

    method = (request.get("method") if isinstance(request, dict) else "GET").upper()
    path = request.get("path", "/") if isinstance(request, dict) else "/"
    body = _parse_body(request)
    query = request.get("queryStringParameters") or {}

    with session_scope() as db:
        try:
            user = _current_user(request)
            workspace_id = user["workspace_id"]

            # GET /contacts
            if method == "GET" and path == "/contacts":
                from shared.services.contacts import list_contacts  # noqa: E402

                items, total = list_contacts(
                    db,
                    workspace_id=workspace_id,
                    search=query.get("search"),
                    limit=int(query.get("limit", 50)),
                    offset=int(query.get("offset", 0)),
                )
                return _response(200, {"items": [i.__dict__ for i in items], "total": total})

            # POST /contacts
            if method == "POST" and path == "/contacts":
                from shared.services.contacts import create_contact  # noqa: E402

                contact = create_contact(db, workspace_id=workspace_id, data=body)
                return _response(201, contact.__dict__)

            # GET /contacts/{id}
            if method == "GET" and path.startswith("/contacts/"):
                from shared.services.contacts import get_contact_or_404  # noqa: E402

                contact_id = path.rsplit("/", 1)[-1]
                contact = get_contact_or_404(db, workspace_id=workspace_id, contact_id=contact_id)
                return _response(200, contact.__dict__)

            # POST /contacts/import (dry-run or commit)
            if method == "POST" and path == "/contacts/import":
                from shared.services.imports import preview_import, commit_import  # noqa: E402

                dry_run = body.get("dry_run", True)
                if dry_run:
                    result = preview_import(db, workspace_id=workspace_id, file_data=body.get("file_data", ""))
                else:
                    result = commit_import(db, workspace_id=workspace_id, file_data=body.get("file_data", ""))
                return _response(200, result.__dict__)

            # GET /contacts/{id}/eligibility
            if method == "GET" and "/eligibility" in path:
                from shared.services.consent import eligibility  # noqa: E402

                contact_id = path.split("/")[-3]
                contact = __import__(
                    "shared.models.contact", fromlist=["Contact"]
                ).Contact
                contact = db.get(contact, contact_id)
                if contact is None:
                    return _error_response(404, "contact_not_found", "Contact not found.")
                return _response(200, eligibility(db, contact=contact).__dict__)

            return _error_response(404, "not_found", "Contacts endpoint not found.")

        except AppError as exc:
            return _error_response(exc.status_code, exc.code, exc.message)
        except Exception:  # pragma: no cover - defensive
            return _error_response(500, "internal_error", "Internal server error.")
