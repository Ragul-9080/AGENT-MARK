from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.deps import CurrentUser, DbSession
from app.core.errors import AppError
from app.core.pagination import Pagination, get_pagination
from app.models.enums import EmailMessageStatus
from app.models.workspace import Workspace
from app.schemas.email import (
    EmailMessageOut,
    EmailSend,
    EmailSendResult,
    EmailWebhookEvent,
)
from app.services import email as email_service
from app.services import webhooks as webhook_service

router = APIRouter(prefix="/email", tags=["email"])

PaginationDep = Annotated[Pagination, Depends(get_pagination)]


@router.post("/send", response_model=EmailSendResult, status_code=202)
def send_email(
    payload: EmailSend,
    user: CurrentUser,
    db: DbSession,
) -> EmailSendResult:
    """Send a single email to a workspace contact.

    Requires email consent (granted) and no suppression for the address.
    The message is queued and delivered by a background worker.
    """
    message = email_service.send_email(
        db,
        workspace_id=user.workspace_id,
        data=payload,
        actor_id=user.id,
    )
    return EmailSendResult(
        message_id=message.id,
        status=message.status,
        provider_message_id=message.provider_message_id,
    )


@router.get("/messages", response_model=list[EmailMessageOut])
def list_email_messages(
    user: CurrentUser,
    db: DbSession,
    pagination: PaginationDep,
    campaign_id: Annotated[uuid.UUID | None, Query()] = None,
    contact_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[EmailMessageStatus | None, Query()] = None,
) -> list[EmailMessageOut]:
    items, _total = email_service.list_email_messages(
        db,
        workspace_id=user.workspace_id,
        campaign_id=campaign_id,
        contact_id=contact_id,
        status=status,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return [EmailMessageOut.model_validate(item) for item in items]


@router.get("/messages/{message_id}", response_model=EmailMessageOut)
def get_email_message(
    message_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> EmailMessageOut:
    message = email_service.get_email_message_or_404(
        db, workspace_id=user.workspace_id, message_id=message_id
    )
    return EmailMessageOut.model_validate(message)


@router.post("/webhooks", status_code=204)
async def email_webhooks(
    request: Request,
    db: DbSession,
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
    token: Annotated[str | None, Query()] = None,
) -> Response:
    """Inbound provider webhook (SES event notifications).

    Authenticated by workspace-scoped query params, since providers call back
    without user sessions. The raw body is stored and the workspace HMAC token
    is verified before any parsing, matching the common webhook router.
    """

    if workspace_id is None or token is None:
        raise AppError(401, "unauthorized", "Workspace webhook params required.")

    webhook_service.verify_workspace_token(workspace_id, token)
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise AppError(404, "workspace_not_found", "We could not find that workspace.")

    raw_body = await request.body()
    delivery = webhook_service.store_delivery(
        db,
        workspace=workspace,
        provider="email",
        request=request,
        raw_body=raw_body,
    )

    # Parse the stored payload into a typed webhook event and process it.
    payload = delivery.payload
    event = EmailWebhookEvent(
        event_type=str(payload.get("eventType") or payload.get("EventType") or "unknown"),
        message_id=str(payload.get("mail", {}).get("messageId", "") or "") or None,
        recipient=str(payload.get("mail", {}).get("destination", [""])[0]) or None,
        meta=payload,
    )
    email_service.record_webhook_event(
        db,
        workspace_id=workspace_id,
        event=event,
    )

    delivery.processed = True
    db.flush()
    return Response(status_code=204)
