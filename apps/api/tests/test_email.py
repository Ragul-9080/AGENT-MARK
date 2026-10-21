from __future__ import annotations

import asyncio
import uuid

import pytest
from app.core.errors import AppError
from app.integrations.email import ConsoleEmailProvider, get_email_provider
from app.models.contact import Contact
from app.models.email import EmailEvent
from app.models.enums import (
    ConsentChannel,
    ConsentStatus,
    EmailEventType,
    EmailMessageStatus,
    SuppressionReason,
)
from app.schemas.contact import ConsentUpsert, SuppressionCreate
from app.schemas.email import EmailSend, EmailWebhookEvent
from app.services import consent as consent_service
from app.services import email as email_service
from app.services.contacts import normalize_email
from sqlalchemy import select


def test_console_provider_does_not_log_pii(caplog) -> None:
    provider = ConsoleEmailProvider()
    assert provider.name() == "console"

    with caplog.at_level("INFO"):
        message_id = asyncio.run(
            provider.send(
                to="user@example.com",
                subject="Hello",
                body_html="<p>Hi</p>",
                body_text="Hi",
            )
        )

    assert message_id.startswith("console-")
    log_text = caplog.text
    assert "user@example.com" not in log_text
    assert "Hello" not in log_text
    assert "Hi" not in log_text
    assert "provider=console" in log_text


def test_get_email_provider_returns_console_by_default() -> None:
    provider = get_email_provider()
    assert isinstance(provider, ConsoleEmailProvider)


def _make_contact(db, workspace_id: uuid.UUID, email: str, name: str = "Contact") -> Contact:
    contact = Contact(id=uuid.uuid4(), workspace_id=workspace_id, name=name, email=email)
    db.add(contact)
    db.flush()
    return contact


def test_send_email_requires_consent(db, account: dict) -> None:
    workspace_id = uuid.UUID(account["workspace"]["id"])
    _make_contact(db, workspace_id, "noconsent@example.com", "No Consent")

    with pytest.raises(AppError) as excinfo:
        email_service.send_email(
            db,
            workspace_id=workspace_id,
            data=EmailSend(
                to="noconsent@example.com",
                subject="Hi",
                body_html="<p>Hi</p>",
            ),
        )
    assert excinfo.value.status_code == 409


def test_send_email_blocked_by_suppression(db, account: dict) -> None:
    workspace_id = uuid.UUID(account["workspace"]["id"])
    contact = _make_contact(db, workspace_id, "suppressed@example.com", "Suppressed")

    consent_service.upsert_consent(
        db,
        contact=contact,
        channel=ConsentChannel.email,
        data=ConsentUpsert(status=ConsentStatus.granted, proof="web"),
    )
    consent_service.create_suppression(
        db,
        workspace_id=workspace_id,
        data=SuppressionCreate(
            channel=ConsentChannel.email,
            value="suppressed@example.com",
            reason=SuppressionReason.unsubscribe,
        ),
    )

    with pytest.raises(AppError) as excinfo:
        email_service.send_email(
            db,
            workspace_id=workspace_id,
            data=EmailSend(
                to="suppressed@example.com",
                subject="Hi",
                body_html="<p>Hi</p>",
            ),
        )
    assert excinfo.value.status_code == 409


def test_send_email_creates_queued_message(db, account: dict) -> None:
    workspace_id = uuid.UUID(account["workspace"]["id"])
    contact = _make_contact(db, workspace_id, "ready@example.com", "Ready")

    consent_service.upsert_consent(
        db,
        contact=contact,
        channel=ConsentChannel.email,
        data=ConsentUpsert(status=ConsentStatus.granted, proof="web form"),
    )

    message = email_service.send_email(
        db,
        workspace_id=workspace_id,
        data=EmailSend(
            to="ready@example.com",
            subject="Welcome",
            body_html="<p>Welcome!</p>",
            body_text="Welcome!",
        ),
        actor_id=uuid.UUID(account["user"]["id"]),
    )

    assert message.status == EmailMessageStatus.queued
    assert message.subject == "Welcome"
    assert message.contact_id == contact.id
    assert message.workspace_id == workspace_id


def test_send_email_unknown_contact_404(db, account: dict) -> None:
    workspace_id = uuid.UUID(account["workspace"]["id"])

    with pytest.raises(AppError) as excinfo:
        email_service.send_email(
            db,
            workspace_id=workspace_id,
            data=EmailSend(
                to="unknown@example.com",
                subject="Hi",
                body_html="<p>Hi</p>",
            ),
        )
    assert excinfo.value.status_code == 404


def test_list_email_messages_workspace_scoped(db, account: dict, other_account: dict) -> None:
    workspace_id = uuid.UUID(account["workspace"]["id"])
    other_workspace_id = uuid.UUID(other_account["workspace"]["id"])

    contact_a = _make_contact(db, workspace_id, "a@example.com", "A")
    contact_b = _make_contact(db, other_workspace_id, "b@example.com", "B")

    consent_service.upsert_consent(
        db,
        contact=contact_a,
        channel=ConsentChannel.email,
        data=ConsentUpsert(status=ConsentStatus.granted, proof="web"),
    )
    consent_service.upsert_consent(
        db,
        contact=contact_b,
        channel=ConsentChannel.email,
        data=ConsentUpsert(status=ConsentStatus.granted, proof="web"),
    )

    m1 = email_service.send_email(
        db,
        workspace_id=workspace_id,
        data=EmailSend(to="a@example.com", subject="One", body_html="<p>1</p>"),
    )
    m2 = email_service.send_email(
        db,
        workspace_id=other_workspace_id,
        data=EmailSend(to="b@example.com", subject="Two", body_html="<p>2</p>"),
    )
    db.commit()

    items, total = email_service.list_email_messages(db, workspace_id=workspace_id)
    assert total == 1
    assert items[0].id == m1.id

    items2, total2 = email_service.list_email_messages(db, workspace_id=other_workspace_id)
    assert total2 == 1
    assert items2[0].id == m2.id


def test_get_email_message_404_for_foreign(db, account: dict, other_account: dict) -> None:
    workspace_id = uuid.UUID(account["workspace"]["id"])
    other_workspace_id = uuid.UUID(other_account["workspace"]["id"])

    contact = _make_contact(db, workspace_id, "x@example.com", "X")

    consent_service.upsert_consent(
        db,
        contact=contact,
        channel=ConsentChannel.email,
        data=ConsentUpsert(status=ConsentStatus.granted, proof="web"),
    )

    message = email_service.send_email(
        db,
        workspace_id=workspace_id,
        data=EmailSend(to="x@example.com", subject="X", body_html="<p>x</p>"),
    )
    db.commit()

    with pytest.raises(AppError) as excinfo:
        email_service.get_email_message_or_404(
            db, workspace_id=other_workspace_id, message_id=message.id
        )
    assert excinfo.value.status_code == 404

    with pytest.raises(AppError) as excinfo:
        email_service.get_email_message_or_404(
            db, workspace_id=workspace_id, message_id=uuid.uuid4()
        )
    assert excinfo.value.status_code == 404


def test_record_webhook_event_updates_status(db, account: dict) -> None:
    workspace_id = uuid.UUID(account["workspace"]["id"])

    contact = _make_contact(db, workspace_id, "w@example.com", "W")

    consent_service.upsert_consent(
        db,
        contact=contact,
        channel=ConsentChannel.email,
        data=ConsentUpsert(status=ConsentStatus.granted, proof="web"),
    )

    message = email_service.send_email(
        db,
        workspace_id=workspace_id,
        data=EmailSend(to="w@example.com", subject="W", body_html="<p>w</p>"),
    )
    message.provider_message_id = "ses-msg-123"
    db.flush()

    updated = email_service.record_webhook_event(
        db,
        workspace_id=workspace_id,
        event=EmailWebhookEvent(
            event_type="delivery",
            message_id="ses-msg-123",
            recipient="w@example.com",
            meta={"timestamp": "2026-01-01T00:00:00Z"},
        ),
    )

    assert updated is not None
    assert updated.status == EmailMessageStatus.delivered

    events = list(db.scalars(select(EmailEvent).where(EmailEvent.message_id == message.id)))
    assert len(events) >= 1
    assert events[0].type == EmailEventType.delivered


def test_record_webhook_event_unknown_message_returns_none(db, account: dict) -> None:
    workspace_id = uuid.UUID(account["workspace"]["id"])
    result = email_service.record_webhook_event(
        db,
        workspace_id=workspace_id,
        event=EmailWebhookEvent(event_type="delivery", message_id="does-not-exist"),
    )
    assert result is None


def test_normalize_email() -> None:
    assert normalize_email("  User@Example.COM ") == "user@example.com"
    assert normalize_email("") is None
    with pytest.raises(AppError):
        normalize_email("not-an-email")
