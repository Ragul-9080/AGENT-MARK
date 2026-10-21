from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query

from app.core.errors import AppError


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def get_pagination(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


def validate_calling_window(value: str) -> tuple[str, str]:
    """Validate a 'HH:MM-HH:MM' 24h window and return its parts."""

    try:
        start_raw, end_raw = value.split("-", 1)
        start_h, start_m = (int(part) for part in start_raw.strip().split(":"))
        end_h, end_m = (int(part) for part in end_raw.strip().split(":"))
    except (ValueError, AttributeError) as exc:
        raise AppError(
            422,
            "invalid_calling_window",
            "Calling hours must use the format 09:00-21:00.",
        ) from exc

    if not (0 <= start_h <= 23 and 0 <= end_h <= 23 and 0 <= start_m <= 59 and 0 <= end_m <= 59):
        raise AppError(422, "invalid_calling_window", "Calling hours contain an invalid time.")
    if (start_h, start_m) >= (end_h, end_m):
        raise AppError(
            422,
            "invalid_calling_window",
            "Calling hours must start before they end.",
        )
    return f"{start_h:02d}:{start_m:02d}", f"{end_h:02d}:{end_m:02d}"
