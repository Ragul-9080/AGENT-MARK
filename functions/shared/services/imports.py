"""Import service for Catalyst functions.

CSV parse/preview/commit with duplicate detection.
Adapted from apps/api/app/services/imports.py.
"""

from __future__ import annotations

import csv
import io
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from shared.core.errors import AppError
from shared.models.contact import Contact
from shared.services.contacts import _normalize_email, _normalize_phone, _normalize_tags


def preview_import(
    db: Session, *, workspace_id: uuid.UUID, file_data: str
) -> dict[str, Any]:
    """Dry-run CSV preview. Returns per-row status without writing."""
    reader = csv.DictReader(io.StringIO(file_data))
    rows = list(reader)
    preview = []
    valid = 0
    invalid = 0
    duplicates = 0

    for idx, row in enumerate(rows, start=1):
        name = (row.get("name") or "").strip() or None
        phone = _normalize_phone(row.get("phone"))
        email = _normalize_email(row.get("email"))

        if not phone and not email:
            preview.append({"row": idx, "status": "invalid", "message": "No phone or email"})
            invalid += 1
            continue

        existing = db.scalar(
            select(Contact).where(
                Contact.workspace_id == workspace_id,
                Contact.email == email if email else False,
            )
        )
        if existing is not None:
            preview.append({"row": idx, "status": "duplicate", "message": "Already exists"})
            duplicates += 1
            continue

        preview.append({"row": idx, "status": "valid", "message": "Ready to import"})
        valid += 1

    return {
        "dry_run": True,
        "total_rows": len(rows),
        "valid_rows": valid,
        "duplicate_rows": duplicates,
        "invalid_rows": invalid,
        "created": 0,
        "preview": preview,
    }


def commit_import(
    db: Session, *, workspace_id: uuid.UUID, file_data: str
) -> dict[str, Any]:
    """Import CSV rows, skipping duplicates."""
    reader = csv.DictReader(io.StringIO(file_data))
    rows = list(reader)
    created = 0
    duplicates = 0

    for row in rows:
        name = (row.get("name") or "").strip() or None
        phone = _normalize_phone(row.get("phone"))
        email = _normalize_email(row.get("email"))

        if not phone and not email:
            continue

        existing = db.scalar(
            select(Contact).where(
                Contact.workspace_id == workspace_id,
                or_(Contact.phone == phone) if phone else False,
            )
        )
        if existing is not None:
            duplicates += 1
            continue

        contact = Contact(
            workspace_id=workspace_id,
            name=name,
            phone=phone,
            email=email,
            language=(row.get("language") or None),
            tags=_normalize_tags([row.get("tags", "")]),
            source=row.get("source"),
            custom_fields={},
        )
        db.add(contact)
        created += 1

    db.flush()
    return {
        "dry_run": False,
        "total_rows": len(rows),
        "valid_rows": created,
        "duplicate_rows": duplicates,
        "invalid_rows": len(rows) - created - duplicates,
        "created": created,
        "preview": [],
    }
