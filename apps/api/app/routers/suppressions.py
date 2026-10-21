from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import Pagination, get_pagination
from app.models.enums import ConsentChannel
from app.schemas.common import Page
from app.schemas.contact import SuppressionCreate, SuppressionOut
from app.services import consent as consent_service

router = APIRouter(prefix="/suppressions", tags=["suppressions"])

PaginationDep = Annotated[Pagination, Depends(get_pagination)]


@router.get("", response_model=Page[SuppressionOut])
def list_suppressions(
    user: CurrentUser,
    db: DbSession,
    pagination: PaginationDep,
    channel: Annotated[ConsentChannel | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[SuppressionOut]:
    items, total = consent_service.list_suppressions(
        db,
        workspace_id=user.workspace_id,
        channel=channel,
        search=search,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return Page[SuppressionOut](
        items=[SuppressionOut.model_validate(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=SuppressionOut, status_code=201)
def create_suppression(
    payload: SuppressionCreate, user: CurrentUser, db: DbSession
) -> SuppressionOut:
    suppression = consent_service.create_suppression(
        db, workspace_id=user.workspace_id, data=payload
    )
    return SuppressionOut.model_validate(suppression)


@router.delete("/{suppression_id}", status_code=204)
def delete_suppression(suppression_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    suppression = consent_service.get_suppression_or_404(
        db, workspace_id=user.workspace_id, suppression_id=suppression_id
    )
    consent_service.delete_suppression(db, workspace_id=user.workspace_id, suppression=suppression)
    return Response(status_code=204)
