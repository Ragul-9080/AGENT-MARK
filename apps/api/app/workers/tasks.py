from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import session_scope
from app.integrations.email import get_email_provider
from app.models.email import EmailMessage, EmailMessageStatus
from app.models.enums import EventModule
from app.models.job import Job
from app.services.campaigns import promote_due_campaigns
from app.services.events import record_event
from app.services.jobs import (
    mark_dead_letter,
    mark_failed,
    mark_running,
    mark_succeeded,
)
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="system.ping", max_retries=3, default_retry_delay=2)
def ping_job(self: Any, job_id: str) -> dict[str, Any]:
    """Health-check task that proves the queue, job progress and retry path."""

    job_uuid = uuid.UUID(job_id)
    with session_scope() as db:
        job = db.get(Job, job_uuid)
        if job is None:
            return {"status": "missing"}
        mark_running(db, job, 10)

    try:
        time.sleep(0.05)
        with session_scope() as db:
            job = db.get(Job, job_uuid)
            if job is None:
                return {"status": "missing"}
            mark_succeeded(db, job, {"pong": True})
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover - defensive retry path
        retries = int(self.request.retries)
        with session_scope() as db:
            job = db.get(Job, job_uuid)
            if job is not None:
                if retries >= int(self.max_retries):
                    mark_dead_letter(db, job, str(exc))
                else:
                    mark_failed(db, job, str(exc))
        if retries < int(self.max_retries):
            raise self.retry(exc=exc, countdown=2**retries) from exc
        return {"status": "dead_letter"}


@celery_app.task(name="app.workers.tasks.promote_scheduled_campaigns")
def promote_scheduled_campaigns() -> dict[str, Any]:
    with session_scope() as db:
        campaign_ids = promote_due_campaigns(db)
    return {"promoted": [str(campaign_id) for campaign_id in campaign_ids]}


@celery_app.task(name="email.send", max_retries=3, default_retry_delay=5)
def send_email_task(message_id: str, actor_id: str | None = None) -> dict[str, Any]:
    """Deliver a queued EmailMessage through the configured provider.

    Updates the message status and records an email.sent / email.failed event.
    The provider receives the actual recipient/subject/body but must not log
    them (PII). All logging here uses placeholders only.
    """

    message_uuid = uuid.UUID(message_id)

    # Load message + contact in one query so we have the recipient address.
    with session_scope() as db:
        message = db.scalar(
            select(EmailMessage)
            .where(EmailMessage.id == message_uuid)
            .options(selectinload(EmailMessage.contact))
        )
        if message is None:
            return {"status": "missing"}
        recipient = message.contact.email if message.contact else None
        subject = message.subject
        body_html = message.body_html
        body_text = message.body_text
        workspace_id = message.workspace_id
        contact_id = message.contact_id

    if not recipient:
        with session_scope() as db:
            message = db.get(EmailMessage, message_uuid)
            if message is not None:
                message.status = EmailMessageStatus.failed
                db.flush()
                record_event(
                    db,
                    workspace_id=workspace_id,
                    source_module=EventModule.email,
                    contact_id=contact_id,
                    type="email.failed",
                    payload={"message_id": str(message.id), "error": "no_recipient_address"},
                )
        return {"status": "failed", "error": "no_recipient_address"}

    provider = get_email_provider()
    try:
        provider_message_id = asyncio.run(
            provider.send(
                to=recipient,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
            )
        )
    except Exception as exc:
        with session_scope() as db:
            message = db.get(EmailMessage, message_uuid)
            if message is None:
                return {"status": "missing"}
            message.status = EmailMessageStatus.failed
            db.flush()
            record_event(
                db,
                workspace_id=message.workspace_id,
                source_module=EventModule.email,
                contact_id=message.contact_id,
                type="email.failed",
                payload={"message_id": str(message.id), "error": str(exc)[:500]},
            )
        return {"status": "failed", "error": str(exc)[:200]}

    with session_scope() as db:
        message = db.get(EmailMessage, message_uuid)
        if message is None:
            return {"status": "missing"}
        message.status = EmailMessageStatus.sent
        message.provider_message_id = provider_message_id
        message.sent_at = datetime.now(UTC)
        db.flush()
        record_event(
            db,
            workspace_id=message.workspace_id,
            source_module=EventModule.email,
            contact_id=message.contact_id,
            type="email.sent",
            payload={"message_id": str(message.id), "provider_message_id": provider_message_id},
        )
    return {"status": "sent", "message_id": str(message_uuid)}
