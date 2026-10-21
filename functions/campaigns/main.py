"""Catalyst function: campaigns.

Campaign CRUD, state machine (draft/scheduled/running/paused/completed/failed),
recipient management, scheduler promotion.
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
    """Catalyst entry point for the campaigns function."""

    method = (request.get("method") if isinstance(request, dict) else "GET").upper()
    path = request.get("path", "/") if isinstance(request, dict) else "/"
    body = _parse_body(request)
    query = request.get("queryStringParameters") or {}

    with session_scope() as db:
        try:
            user = _current_user(request)
            workspace_id = user["workspace_id"]

            # GET /campaigns
            if method == "GET" and path == "/campaigns":
                from shared.services.campaigns import list_campaigns  # noqa: E402

                items, total = list_campaigns(
                    db,
                    workspace_id=workspace_id,
                    limit=int(query.get("limit", 50)),
                    offset=int(query.get("offset", 0)),
                )
                return _response(200, {"items": [i.__dict__ for i in items], "total": total})

            # POST /campaigns
            if method == "POST" and path == "/campaigns":
                from shared.services.campaigns import create_campaign  # noqa: E402

                campaign = create_campaign(db, workspace_id=workspace_id, data=body)
                return _response(201, campaign.__dict__)

            # Campaign actions: /campaigns/{id}/start|pause|resume|stop
            if method == "POST" and "/campaigns/" in path:
                from shared.services.campaigns import (  # noqa: E402
                    get_campaign_or_404,
                    start_campaign,
                    pause_campaign,
                    resume_campaign,
                    stop_campaign,
                )

                segments = path.split("/")
                campaign_id = segments[2]
                action = segments[3] if len(segments) > 3 else ""
                campaign = get_campaign_or_404(db, workspace_id=workspace_id, campaign_id=campaign_id)

                if action == "start":
                    campaign = start_campaign(db, campaign=campaign, actor_id=user["user_id"])
                elif action == "pause":
                    campaign = pause_campaign(db, campaign=campaign, actor_id=user["user_id"])
                elif action == "resume":
                    campaign = resume_campaign(db, campaign=campaign, actor_id=user["user_id"])
                elif action == "stop":
                    campaign = stop_campaign(db, campaign=campaign, actor_id=user["user_id"])
                else:
                    return _error_response(404, "not_found", "Campaign action not found.")
                return _response(200, campaign.__dict__)

            return _error_response(404, "not_found", "Campaigns endpoint not found.")

        except AppError as exc:
            return _error_response(exc.status_code, exc.code, exc.message)
        except Exception:  # pragma: no cover - defensive
            return _error_response(500, "internal_error", "Internal server error.")
