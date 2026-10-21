"""Contact service for Catalyst functions.

CRUD, search, filters, pagination. Workspace-scoped.
Adapted from apps/api/app/services/contacts.py.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from shared.core.errors import AppError
from shared.models.contact import Contact
from shared.models.enums import ConsentChannel
from shared.schemas.contact import ContactCreate
from shared.services.events import record_event


def _normalize_phone(raw: str | None, default_region: str = "IN") -> str | None:
    if not raw:
        return None
    import phonenumbers

    try:
        parsed = phonenumbers.parse(raw, default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    except Exception:
        return None
    return None


def _normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        from email_validator import validate_email, EmailNotValidError

        return validate_email(value, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        cleaned = tag.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result[:50]


def create_contact(
    db: Session, *, workspace_id: uuid.UUID, data: dict[str, Any]
) -> Contact:
    phone = _normalize_phone(data.get("phone"))
    email = _normalize_email(data.get("email"))

    existing = db.scalar(
        select(Contact).where(
            Contact.workspace_id == workspace_id,
            or_(
                Contact.phone == phone if phone else False,
                Contact.email == email if email else False,
            ),
        )
    )
    if existing is not None:
        raise AppError(409, "duplicate_contact", "A contact with this phone or email already exists.")

    contact = Contact(
        workspace_id=workspace_id,
        name=(data.get("name") or "").strip() or None,
        phone=phone,
        email=email,
        language=data.get("language"),
        tags=_normalize_tags(data.get("tags")),
        source=data.get("source"),
        custom_fields=data.get("custom_fields") or {},
    )
    db.add(contact)
    db.flush()
    record_event(
        db,
        workspace_id=workspace_id,
        source_module="system",
        type="contact.created",
        contact_id=contact.id,
    )
    return contact


def get_contact_or_404(
    db: Session, *, workspace_id: uuid.UUID, contact_id: uuid.UUID
) -> Contact:
    contact = db.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    )
    if contact is None:
        raise AppError(404, "contact_not_found", "We could not find that contact.")
    return contact


def list_contacts(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Contact], int]:
    stmt = select(Contact).where(Contact.workspace_id == workspace_id)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Contact.name.ilike(term),
                Contact.phone.ilike(term),
                Contact.email.ilike(term),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.order_by(Contact.created_at.desc(), Contact.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total
