from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.core.deps import DbSession
from app.core.errors import AppError
from app.models.workspace import Workspace
from app.services import webhooks as webhook_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

MAX_WEBHOOK_BYTES = 1024 * 1024


@router.post("/{provider}")
async def receive_webhook(
    provider: str,
    request: Request,
    db: DbSession,
    workspace_id: Annotated[uuid.UUID, Query()],
    token: Annotated[str, Query()],
) -> dict[str, str]:
    if provider not in {"vobiz", "email"}:
        raise AppError(404, "unknown_provider", "Unknown webhook provider.")

    webhook_service.verify_workspace_token(workspace_id, token)
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise AppError(404, "workspace_not_found", "We could not find that workspace.")

    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BYTES:
        raise AppError(413, "payload_too_large", "The callback payload is too large.")

    delivery = webhook_service.store_delivery(
        db,
        workspace=workspace,
        provider=provider,
        request=request,
        raw_body=raw_body,
    )
    return {"status": "accepted", "id": str(delivery.id)}
