"""Import every model so Alembic and the app see complete metadata."""

from app.models.base import Base
from app.models.campaign import Campaign, CampaignContact
from app.models.consent import Consent, Suppression
from app.models.contact import Contact
from app.models.email import EmailEvent, EmailMessage
from app.models.event import Event
from app.models.job import Job, WebhookDelivery
from app.models.seo import SeoAudit, SeoIssue, SeoRecommendation, Website
from app.models.user import User
from app.models.voice import Call, CallTurn
from app.models.workspace import Workspace

__all__ = [
    "Base",
    "Call",
    "CallTurn",
    "Campaign",
    "CampaignContact",
    "Consent",
    "Contact",
    "EmailEvent",
    "EmailMessage",
    "Event",
    "Job",
    "SeoAudit",
    "SeoIssue",
    "SeoRecommendation",
    "Suppression",
    "User",
    "WebhookDelivery",
    "Website",
    "Workspace",
]
