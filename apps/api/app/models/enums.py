from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class UserRole(StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


class ConsentChannel(StrEnum):
    voice = "voice"
    email = "email"


class ConsentStatus(StrEnum):
    granted = "granted"
    revoked = "revoked"


class SuppressionReason(StrEnum):
    dnd = "dnd"
    unsubscribe = "unsubscribe"
    bounce = "bounce"
    complaint = "complaint"
    manual = "manual"


class CampaignType(StrEnum):
    voice = "voice"
    email = "email"


class CampaignStatus(StrEnum):
    draft = "draft"
    scheduled = "scheduled"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"


class CampaignContactStatus(StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"
    failed = "failed"


class CallDirection(StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class CallOutcome(StrEnum):
    interested = "interested"
    not_interested = "not_interested"
    callback = "callback"
    wrong_number = "wrong_number"
    no_answer = "no_answer"
    voicemail = "voicemail"
    handoff = "handoff"


class Sentiment(StrEnum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class CallSpeaker(StrEnum):
    agent = "agent"
    contact = "contact"


class EmailMessageStatus(StrEnum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    bounced = "bounced"
    complained = "complained"
    failed = "failed"


class EmailEventType(StrEnum):
    delivered = "delivered"
    open = "open"
    click = "click"
    bounce = "bounce"
    complaint = "complaint"
    reply = "reply"
    unsubscribe = "unsubscribe"


class SeoAuditStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class SeoIssueSeverity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class SeoRecommendationStatus(StrEnum):
    proposed = "proposed"
    accepted = "accepted"
    dismissed = "dismissed"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    dead_letter = "dead_letter"


class EventModule(StrEnum):
    system = "system"
    voice = "voice"
    email = "email"
    seo = "seo"


def enum_column_type(enum_class: type[StrEnum], name: str, length: int = 32) -> SAEnum:
    """Portable enum storage (VARCHAR + CHECK) to keep migrations simple."""

    return SAEnum(
        enum_class,
        name=name,
        native_enum=False,
        length=length,
        create_constraint=True,
        validate_strings=True,
    )
