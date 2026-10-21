"""Email schemas for Catalyst functions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field

from shared.models.enums import EmailEventType, EmailMessageStatus
from shared.schemas.common import ORMModel


class EmailSend(ORMModel):
    to: EmailStr
    subject: str = Field(min_length=1, max_length=500)
    body_html: str | None = Field(default=None, max_length=1_000_000)
    body_text: str | None = Field(default=None, max_length=1_000_000)
    campaign_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None


class EmailSendResult(ORMModel):
    message_id: uuid.UUID
    status: EmailMessageStatus
    provider_message_id: str | None = None


class EmailMessageOut(ORMModel):
    id: uuid.UUID
    campaign_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    subject: str
    body_html: str
    body_text: str | None
    provider_message_id: str | None
    status: EmailMessageStatus
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EmailEventOut(ORMModel):
    id: uuid.UUID
    message_id: uuid.UUID
    type: EmailEventType
    occurred_at: datetime
    meta: dict[str, Any]


class EmailWebhookEvent(ORMModel):
    event_type: str = Field(max_length=100)
    message_id: str | None = Field(default=None, max_length=255)
    recipient: str | None = Field(default=None, max_length=320)
    meta: dict[str, Any] = Field(default_factory=dict)
