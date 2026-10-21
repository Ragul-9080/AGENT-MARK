"""Pagination helpers for Catalyst functions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Pagination:
    limit: int
    offset: int


def get_pagination(limit: int = 50, offset: int = 0) -> Pagination:
    if limit < 1 or limit > 1000:
        limit = 50
    if offset < 0:
        offset = 0
    return Pagination(limit=limit, offset=offset)


def validate_calling_window(value: str) -> tuple[str, str]:
    """Validate a HH:MM-HH:MM calling window string."""
    parts = value.split("-")
    if len(parts) != 2:
        from shared.core.errors import AppError

        raise AppError(422, "invalid_calling_window", "Use HH:MM-HH:MM format.")

    try:
        start = parts[0].zfill(5)
        end = parts[1].zfill(5)
        int(start.split(":")[0])
        int(start.split(":")[1])
        int(end.split(":")[0])
        int(end.split(":")[1])
    except ValueError as exc:
        from shared.core.errors import AppError

        raise AppError(422, "invalid_calling_window", "Use HH:MM-HH:MM format.") from exc

    return start, end
