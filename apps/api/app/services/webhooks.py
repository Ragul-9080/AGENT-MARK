from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any
from urllib.parse import parse_qs

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models.job import WebhookDelivery
from app.models.workspace import Workspace


def workspace_webhook_token(workspace_id: uuid.UUID) -> str:
    """Signed workspace context for provider callback URLs."""

    message = f"webhook:{workspace_id}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def verify_workspace_token(workspace_id: uuid.UUID, token: str) -> None:
    expected = workspace_webhook_token(workspace_id)
    if not hmac.compare_digest(expected, token):
        raise AppError(401, "invalid_webhook_token", "This callback URL is not valid.")


def _provider_signature(provider: str, headers: dict[str, str]) -> str | None:
    if provider == "vobiz":
        return headers.get("x-vobiz-signature-v3") or headers.get("x-vobiz-signature-v2")
    if provider == "email":
        return headers.get("x-webhook-signature")
    return None


def verify_provider_signature(
    provider: str, *, headers: dict[str, str], raw_body: bytes
) -> tuple[bool, str | None]:
    """Verify a provider HMAC when a secret is configured.

    The exact Vobiz V2/V3 canonicalisation is implemented in Milestone 4 after reading
    https://www.vobiz.ai/docs/concepts/validating-callbacks. Until then a configured secret
    is treated as a plain HMAC-SHA256 over the raw body, which is the documented fallback
    used by the common webhook router. Email/SES SNS signature verification lands with the
    email adapter in Milestone 2.
    """

    secret = settings.vobiz_webhook_secret if provider == "vobiz" else settings.email_webhook_secret
    if not secret:
        if settings.is_production:
            raise AppError(
                503,
                "webhook_not_configured",
                "This callback endpoint is not configured for this environment.",
            )
        return False, "verification_not_configured"

    signature = _provider_signature(provider, headers)
    if not signature:
        return False, "missing_signature"

    candidate = signature.split("=", 1)[-1].strip()
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, candidate):
        return False, "invalid_signature"
    return True, None


def _parse_payload(raw_body: bytes, content_type: str) -> dict[str, Any]:
    if "application/json" in content_type:
        try:
            payload = json.loads(raw_body.decode("utf-8"))
            if isinstance(payload, dict):
                return payload
            return {"value": payload}
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

    if "application/x-www-form-urlencoded" in content_type:
        try:
            parsed = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
            return {
                key: values[0] if len(values) == 1 else values for key, values in parsed.items()
            }
        except UnicodeDecodeError:
            pass

    return {"raw": raw_body.decode("utf-8", errors="replace")[:20_000]}


def store_delivery(
    db: Session,
    *,
    workspace: Workspace,
    provider: str,
    request: Request,
    raw_body: bytes,
) -> WebhookDelivery:
    content_type = request.headers.get("content-type", "")
    payload = _parse_payload(raw_body, content_type)
    signature_valid, error = verify_provider_signature(
        provider,
        headers={key.lower(): value for key, value in request.headers.items()},
        raw_body=raw_body,
    )

    event_type = (
        str(
            payload.get("Event")
            or payload.get("event")
            or payload.get("type")
            or payload.get("notificationType")
            or ""
        )[:100]
        or None
    )

    delivery = WebhookDelivery(
        workspace_id=workspace.id,
        provider=provider,
        event_type=event_type,
        payload=payload,
        signature_valid=signature_valid,
        processed=False,
        error=error,
    )
    db.add(delivery)
    db.flush()

    if not signature_valid:
        # Commit the audit record before returning the 401; the request session would
        # otherwise roll it back when the error propagates.
        db.commit()
        raise AppError(
            401,
            "invalid_webhook_signature",
            "The callback signature could not be verified.",
        )
    return delivery
