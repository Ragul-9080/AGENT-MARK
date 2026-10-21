"""Webhook service for Catalyst functions.

Workspace-scoped webhook receiver with HMAC token verification.
Adapted from apps/api/app/services/webhooks.py.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from shared.core.config import settings
from shared.core.errors import AppError
from shared.models.job import WebhookDelivery
from shared.models.workspace import Workspace


def workspace_webhook_token(workspace_id: uuid.UUID) -> str:
    """Signed workspace context for provider callback URLs."""
    message = f"webhook:{workspace_id}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def verify_workspace_token(workspace_id: uuid.UUID, token: str) -> None:
    expected = workspace_webhook_token(workspace_id)
    if not hmac.compare_digest(expected, token):
        raise AppError(401, "invalid_webhook_token", "This callback URL is not valid.")


def store_delivery(
    db: Session,
    *,
    workspace: Workspace,
    provider: str,
    request: Any,
    raw_body: bytes,
) -> WebhookDelivery:
    content_type = getattr(request, "headers", {}).get("content-type", "")
    payload: dict[str, Any] = {}
    if "application/json" in content_type:
        try:
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict):
                payload = {"value": payload}
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"raw": raw_body.decode("utf-8", errors="replace")[:20_000]}
    else:
        payload = {"raw": raw_body.decode("utf-8", errors="replace")[:20_000]}

    event_type = str(
        payload.get("Event")
        or payload.get("event")
        or payload.get("type")
        or payload.get("notificationType")
        or ""
    )[:100] or None

    delivery = WebhookDelivery(
        workspace_id=workspace.id,
        provider=provider,
        event_type=event_type,
        payload=payload,
        signature_valid=False,
        processed=False,
        error=None,
    )
    db.add(delivery)
    db.flush()
    return delivery
