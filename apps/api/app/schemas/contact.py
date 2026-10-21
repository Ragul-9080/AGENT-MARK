from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field, model_validator

from app.models.enums import ConsentChannel, ConsentStatus, SuppressionReason
from app.schemas.common import ORMModel


class ContactCreate(ORMModel):
    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    language: str | None = Field(default=None, max_length=16)
    tags: list[str] = Field(default_factory=list, max_length=50)
    source: str | None = Field(default=None, max_length=64)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_phone_or_email(self) -> ContactCreate:
        if not (self.phone or "").strip() and not self.email:
            raise ValueError("Provide a phone number or an email address")
        return self


class ContactUpdate(ORMModel):
    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    language: str | None = Field(default=None, max_length=16)
    tags: list[str] | None = Field(default=None, max_length=50)
    source: str | None = Field(default=None, max_length=64)
    custom_fields: dict[str, Any] | None = None


class ContactOut(ORMModel):
    id: uuid.UUID
    name: str | None
    phone: str | None
    email: str | None
    language: str | None
    tags: list[str]
    source: str | None
    custom_fields: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ConsentOut(ORMModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    channel: ConsentChannel
    status: ConsentStatus
    proof: str | None
    recorded_at: datetime


class ConsentUpsert(ORMModel):
    status: ConsentStatus
    proof: str | None = Field(default=None, max_length=2000)
    recorded_at: datetime | None = None


class SuppressionCreate(ORMModel):
    channel: ConsentChannel
    value: str = Field(min_length=1, max_length=320)
    reason: SuppressionReason = SuppressionReason.manual


class SuppressionOut(ORMModel):
    id: uuid.UUID
    channel: ConsentChannel
    value: str
    reason: SuppressionReason
    created_at: datetime


class ChannelEligibility(ORMModel):
    allowed: bool
    reason: str | None = None
    message: str


class EligibilityOut(ORMModel):
    contact_id: uuid.UUID
    voice: ChannelEligibility
    email: ChannelEligibility


class ImportErrorItem(ORMModel):
    row: int
    field: str | None = None
    code: str
    message: str


class ImportPreviewRow(ORMModel):
    row: int
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str
    message: str | None = None


class ImportResult(ORMModel):
    dry_run: bool
    total_rows: int
    valid_rows: int
    duplicate_rows: int
    invalid_rows: int
    created: int
    errors: list[ImportErrorItem]
    preview: list[ImportPreviewRow]
    truncated: bool = False
