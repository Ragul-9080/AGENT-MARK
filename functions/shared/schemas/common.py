"""Shared Pydantic schemas (base classes) for Catalyst functions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ConfigDict


class ORMModel:
    """Base for schemas that validate ORM models."""

    model_config = ConfigDict(from_attributes=True)


class Page:
    """Paginated response wrapper."""

    def __init__(self, items: list[Any], total: int, limit: int, offset: int) -> None:
        self.items = items
        self.total = total
        self.limit = limit
        self.offset = offset
