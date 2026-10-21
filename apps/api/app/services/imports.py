from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models.contact import Contact
from app.models.enums import EventModule
from app.models.workspace import Workspace
from app.schemas.contact import ImportErrorItem, ImportPreviewRow, ImportResult
from app.services.contacts import normalize_email, normalize_phone, normalize_tags
from app.services.events import record_event

KNOWN_COLUMNS = {"name", "phone", "email", "language", "tags", "source"}
PREVIEW_LIMIT = 50
ERROR_LIMIT = 500


@dataclass
class ParsedRow:
    row_number: int
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    language: str | None = None
    source: str = "csv_import"
    tags: list[str] = field(default_factory=list)
    custom_fields: dict[str, str] = field(default_factory=dict)
    status: str = "valid"
    message: str | None = None
    error_field: str | None = None
    error_code: str | None = None


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AppError(422, "invalid_csv", "The file must be UTF-8 encoded text.")


def _clean(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _parse_tags(value: str) -> list[str]:
    if not value:
        return []
    parts = value.replace("|", ",").replace(";", ",").split(",")
    return normalize_tags(parts)


def parse_csv(
    content: bytes, workspace: Workspace
) -> tuple[list[ParsedRow], list[ImportErrorItem]]:
    text = _decode(content)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise AppError(422, "invalid_csv", "The file needs a header row.")

    header_map = {name.strip().lower(): name for name in reader.fieldnames if name}
    if "phone" not in header_map and "email" not in header_map:
        raise AppError(
            422,
            "invalid_csv",
            "The CSV needs at least a phone or email column.",
        )

    rows: list[ParsedRow] = []
    errors: list[ImportErrorItem] = []
    seen_phones: set[str] = set()
    seen_emails: set[str] = set()

    for index, raw_row in enumerate(reader, start=2):
        if len(rows) >= settings.contact_import_max_rows:
            raise AppError(
                422,
                "import_too_large",
                f"The file has more than {settings.contact_import_max_rows} rows. Split it and try again.",
            )

        values = {
            (str(key).strip().lower() if key else ""): value for key, value in raw_row.items()
        }
        if not any(_clean(value) for value in values.values()):
            continue

        parsed = ParsedRow(row_number=index)
        parsed.name = _clean(values.get("name")) or None
        phone_raw = _clean(values.get("phone"))
        email_raw = _clean(values.get("email"))
        parsed.language = _clean(values.get("language")) or workspace.default_language
        parsed.source = _clean(values.get("source")) or "csv_import"
        parsed.tags = _parse_tags(_clean(values.get("tags")))

        for header, value in raw_row.items():
            if header is None:
                continue
            normalized_header = header.strip().lower()
            if normalized_header and normalized_header not in KNOWN_COLUMNS:
                cleaned = _clean(value)
                if cleaned:
                    parsed.custom_fields[header.strip()] = cleaned

        error_field: str | None = None
        error_code: str | None = None
        error_message: str | None = None

        if phone_raw:
            try:
                parsed.phone = normalize_phone(phone_raw)
            except AppError:
                error_field = "phone"
                error_code = "invalid_phone"
                error_message = f"'{phone_raw}' is not a valid phone number."
        if email_raw:
            try:
                parsed.email = normalize_email(email_raw)
            except AppError:
                if error_message is None:
                    error_field = "email"
                    error_code = "invalid_email"
                    error_message = f"'{email_raw}' is not a valid email address."

        if error_message is not None:
            parsed.status = "invalid"
            parsed.message = error_message
            parsed.error_field = error_field
            parsed.error_code = error_code or "invalid_value"
            errors.append(
                ImportErrorItem(
                    row=index,
                    field=parsed.error_field,
                    code=parsed.error_code,
                    message=parsed.message,
                )
            )
        elif parsed.phone is None and parsed.email is None:
            parsed.status = "invalid"
            parsed.message = "Add a phone number or an email address."
            parsed.error_code = "missing_contact_details"
            errors.append(
                ImportErrorItem(
                    row=index,
                    field=None,
                    code="missing_contact_details",
                    message=parsed.message,
                )
            )
        elif (parsed.phone and parsed.phone in seen_phones) or (
            parsed.email and parsed.email in seen_emails
        ):
            parsed.status = "duplicate"
            parsed.message = "This row repeats a phone number or email earlier in the file."
            errors.append(
                ImportErrorItem(
                    row=index,
                    field="phone/email",
                    code="duplicate_in_file",
                    message=parsed.message,
                )
            )
        else:
            if parsed.phone:
                seen_phones.add(parsed.phone)
            if parsed.email:
                seen_emails.add(parsed.email)

        rows.append(parsed)

    return rows, errors


def _mark_database_duplicates(db: Session, workspace_id: uuid.UUID, rows: list[ParsedRow]) -> None:
    phones = [row.phone for row in rows if row.phone and row.status == "valid"]
    emails = [row.email for row in rows if row.email and row.status == "valid"]
    if not phones and not emails:
        return

    conditions = []
    if phones:
        conditions.append(Contact.phone.in_(phones))
    if emails:
        conditions.append(Contact.email.in_(emails))
    existing = db.scalars(
        select(Contact).where(Contact.workspace_id == workspace_id, or_(*conditions))
    ).all()
    existing_phones = {contact.phone for contact in existing if contact.phone}
    existing_emails = {contact.email for contact in existing if contact.email}

    for row in rows:
        if row.status != "valid":
            continue
        if (row.phone and row.phone in existing_phones) or (
            row.email and row.email in existing_emails
        ):
            row.status = "duplicate"
            row.message = "A contact with this phone number or email already exists."


def import_contacts(
    db: Session,
    *,
    workspace: Workspace,
    content: bytes,
    dry_run: bool,
) -> ImportResult:
    if len(content) > settings.contact_import_max_bytes:
        raise AppError(
            422,
            "import_too_large",
            "The file is larger than 5 MB. Split it and try again.",
        )

    rows, errors = parse_csv(content, workspace)
    _mark_database_duplicates(db, workspace.id, rows)

    valid_rows = [row for row in rows if row.status == "valid"]
    duplicate_rows = [row for row in rows if row.status == "duplicate"]
    invalid_rows = [row for row in rows if row.status == "invalid"]

    for row in duplicate_rows:
        if not any(error.row == row.row_number for error in errors):
            errors.append(
                ImportErrorItem(
                    row=row.row_number,
                    field="phone/email",
                    code="duplicate_contact",
                    message=row.message or "Duplicate contact.",
                )
            )

    created = 0
    if not dry_run and valid_rows:
        contacts: list[Contact] = []
        for row in valid_rows:
            contact = Contact(
                workspace_id=workspace.id,
                name=row.name,
                phone=row.phone,
                email=row.email,
                language=row.language,
                tags=row.tags,
                source=row.source[:64],
                custom_fields=row.custom_fields,
            )
            db.add(contact)
            contacts.append(contact)
        db.flush()

        for contact in contacts:
            record_event(
                db,
                workspace_id=workspace.id,
                source_module=EventModule.system,
                type="contact.created",
                contact_id=contact.id,
                payload={"source": contact.source},
            )
        record_event(
            db,
            workspace_id=workspace.id,
            source_module=EventModule.system,
            type="contacts.imported",
            payload={
                "created": len(contacts),
                "duplicates": len(duplicate_rows),
                "invalid": len(invalid_rows),
            },
        )
        created = len(contacts)

    error_items = errors[:ERROR_LIMIT]
    preview = [
        ImportPreviewRow(
            row=row.row_number,
            name=row.name,
            phone=row.phone,
            email=row.email,
            status=row.status,
            message=row.message,
        )
        for row in rows[:PREVIEW_LIMIT]
    ]

    return ImportResult(
        dry_run=dry_run,
        total_rows=len(rows),
        valid_rows=len(valid_rows),
        duplicate_rows=len(duplicate_rows),
        invalid_rows=len(invalid_rows),
        created=created,
        errors=error_items,
        preview=preview,
        truncated=len(rows) > PREVIEW_LIMIT or len(errors) > ERROR_LIMIT,
    )
