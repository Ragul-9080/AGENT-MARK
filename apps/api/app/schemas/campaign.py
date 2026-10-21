from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import (
    CampaignContactStatus,
    CampaignStatus,
    CampaignType,
)
from app.schemas.common import ORMModel
from app.schemas.contact import ContactOut


class CampaignCreate(ORMModel):
    type: CampaignType
    name: str = Field(min_length=1, max_length=200)
    scheduled_at: datetime | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class CampaignUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    scheduled_at: datetime | None = None
    settings: dict[str, Any] | None = None


class CampaignOut(ORMModel):
    id: uuid.UUID
    type: CampaignType
    name: str
    status: CampaignStatus
    scheduled_at: datetime | None
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CampaignContactOut(ORMModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    contact_id: uuid.UUID
    status: CampaignContactStatus
    attempts: int
    last_attempt_at: datetime | None
    contact: ContactOut


class CampaignAddContacts(ORMModel):
    contact_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)


class CampaignAddContactsResult(ORMModel):
    added: int
    skipped: int
    missing: int
