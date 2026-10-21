"""Catalyst function: jobs.

Database-backed job progress, terminal states, and the system.ping health-check
task. Celery is optional -- in Catalyst this maps to Job Scheduling (cron).
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
    """Catalyst entry point for the jobs function."""

    method = (request.get("method") if isinstance(request, dict) else "GET").upper()
    path = request.get("path", "/") if isinstance(request, dict) else "/"
    body = _parse_body(request)
    query = request.get("queryStringParameters") or {}

    with session_scope() as db:
        try:
            user = _current_user(request)
            workspace_id = user["workspace_id"]

            # GET /jobs
            if method == "GET" and path == "/jobs":
                from shared.services.jobs import list_jobs  # noqa: E402

                items, total = list_jobs(
                    db,
                    workspace_id=workspace_id,
                    limit=int(query.get("limit", 50)),
                    offset=int(query.get("offset", 0)),
                )
                return _response(200, {"items": [i.__dict__ for i in items], "total": total})

            # POST /jobs/system.ping (health-check job)
            if method == "POST" and path == "/jobs/system.ping":
                import uuid

                from shared.services.jobs import create_job, mark_succeeded  # noqa: E402
                from shared.models.job import JobStatus  # noqa: E402

                job = create_job(
                    db,
                    workspace_id=workspace_id,
                    type="system.ping",
                    payload={},
                )
                mark_succeeded(db, job, {"pong": True})
                return _response(200, {"status": "ok", "job_id": str(job.id)})

            return _error_response(404, "not_found", "Jobs endpoint not found.")

        except AppError as exc:
            return _error_response(exc.status_code, exc.code, exc.message)
        except Exception:  # pragma: no cover - defensive
            return _error_response(500, "internal_error", "Internal server error.")
