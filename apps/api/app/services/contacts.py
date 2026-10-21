from __future__ import annotations

import re
import uuid

import phonenumbers
from email_validator import EmailNotValidError, validate_email
from phonenumbers import NumberParseException, PhoneNumberFormat
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.contact import Contact
from app.models.enums import EventModule
from app.schemas.contact import ContactCreate, ContactUpdate
from app.services.events import record_event


def normalize_phone(raw: str | None, default_region: str = "IN") -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None

    cleaned = re.sub(r"[^\d+]", "", value)
    if default_region.upper() == "IN" and cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]

    try:
        parsed = phonenumbers.parse(cleaned, default_region)
    except NumberParseException as exc:
        raise AppError(
            422, "invalid_phone", "Enter a valid phone number, including the country code."
        ) from exc

    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
        raise AppError(
            422, "invalid_phone", "Enter a valid phone number, including the country code."
        )

    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)


def normalize_email(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        return validate_email(value, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise AppError(422, "invalid_email", "Enter a valid email address.") from exc


def normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        cleaned = tag.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned[:50])
        if len(result) >= 50:
            break
    return result


def get_contact_or_404(db: Session, workspace_id: uuid.UUID, contact_id: uuid.UUID) -> Contact:
    contact = db.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.workspace_id == workspace_id)
    )
    if contact is None:
        raise AppError(404, "contact_not_found", "We could not find that contact.")
    return contact


def _duplicate_for(
    db: Session,
    workspace_id: uuid.UUID,
    *,
    phone: str | None,
    email: str | None,
    exclude_id: uuid.UUID | None = None,
) -> Contact | None:
    conditions = []
    if phone:
        conditions.append(Contact.phone == phone)
    if email:
        conditions.append(Contact.email == email)
    if not conditions:
        return None

    stmt = select(Contact).where(Contact.workspace_id == workspace_id, or_(*conditions))
    if exclude_id is not None:
        stmt = stmt.where(Contact.id != exclude_id)
    return db.scalar(stmt.limit(1))


def _raise_duplicate(existing: Contact) -> None:
    if existing.phone:
        message = "A contact with that phone number already exists."
    else:
        message = "A contact with that email address already exists."
    raise AppError(
        409,
        "duplicate_contact",
        message,
        details=[{"field": "phone/email", "existing_contact_id": str(existing.id)}],
    )


def create_contact(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    data: ContactCreate,
    source: str | None = None,
    record_created_event: bool = True,
) -> Contact:
    phone = normalize_phone(data.phone)
    email = normalize_email(str(data.email) if data.email else None)
    if phone is None and email is None:
        raise AppError(422, "missing_contact_details", "Provide a phone number or email address.")

    existing = _duplicate_for(db, workspace_id, phone=phone, email=email)
    if existing is not None:
        _raise_duplicate(existing)

    contact = Contact(
        workspace_id=workspace_id,
        name=(data.name or "").strip() or None,
        phone=phone,
        email=email,
        language=data.language,
        tags=normalize_tags(data.tags),
        source=(source or data.source or "manual").strip()[:64],
        custom_fields=data.custom_fields,
    )
    db.add(contact)
    db.flush()

    if record_created_event:
        record_event(
            db,
            workspace_id=workspace_id,
            source_module=EventModule.system,
            type="contact.created",
            contact_id=contact.id,
            payload={"source": contact.source},
        )
    return contact


def update_contact(
    db: Session, *, workspace_id: uuid.UUID, contact: Contact, data: ContactUpdate
) -> Contact:
    updates = data.model_dump(exclude_unset=True)

    phone = contact.phone
    email = contact.email
    if "phone" in updates:
        phone = normalize_phone(updates.pop("phone"))
    if "email" in updates:
        raw_email = updates.pop("email")
        email = normalize_email(str(raw_email) if raw_email else None)

    if phone is None and email is None:
        raise AppError(
            422,
            "missing_contact_details",
            "A contact must keep a phone number or an email address.",
        )

    existing = _duplicate_for(db, workspace_id, phone=phone, email=email, exclude_id=contact.id)
    if existing is not None:
        _raise_duplicate(existing)

    changed_fields: list[str] = []
    contact.phone = phone
    contact.email = email

    if "name" in updates:
        name = updates.pop("name")
        contact.name = (name or "").strip() or None
        changed_fields.append("name")
    if "language" in updates:
        contact.language = updates.pop("language")
        changed_fields.append("language")
    if "tags" in updates:
        contact.tags = normalize_tags(updates.pop("tags"))
        changed_fields.append("tags")
    if "source" in updates:
        source = updates.pop("source")
        contact.source = (source or "").strip()[:64] or None
        changed_fields.append("source")
    if "custom_fields" in updates:
        contact.custom_fields = updates.pop("custom_fields") or {}
        changed_fields.append("custom_fields")

    for field in ("phone", "email"):
        if field in data.model_fields_set:
            changed_fields.append(field)

    record_event(
        db,
        workspace_id=workspace_id,
        source_module=EventModule.system,
        type="contact.updated",
        contact_id=contact.id,
        payload={"fields": sorted(set(changed_fields))},
    )
    db.flush()
    return contact


def delete_contact(db: Session, *, workspace_id: uuid.UUID, contact: Contact) -> None:
    record_event(
        db,
        workspace_id=workspace_id,
        source_module=EventModule.system,
        type="contact.deleted",
        contact_id=contact.id,
        payload={},
    )
    db.delete(contact)
    db.flush()


def list_contacts(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    search: str | None = None,
    tag: str | None = None,
    language: str | None = None,
    source: str | None = None,
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
    if tag:
        stmt = stmt.where(Contact.tags.contains([tag]))
    if language:
        stmt = stmt.where(Contact.language == language)
    if source:
        stmt = stmt.where(Contact.source == source)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.order_by(Contact.created_at.desc(), Contact.id.desc()).limit(limit).offset(offset)
        )
    )
    return items, total
