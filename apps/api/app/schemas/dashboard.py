from __future__ import annotations

from pydantic import Field

from app.schemas.campaign import CampaignOut
from app.schemas.common import ORMModel
from app.schemas.event import EventOut


class DashboardSummary(ORMModel):
    contacts: int
    calls: int
    emails_sent: int
    latest_seo_score: int | None
    running_campaigns: int
    active_campaigns: list[CampaignOut] = Field(default_factory=list)
    recent_events: list[EventOut] = Field(default_factory=list)
