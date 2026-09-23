from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.dependencies import get_budget_for_user, get_db
from app.infrastructure.database.models.overtime import OvertimeEntry
from app.infrastructure.database.models.user import User
from app.infrastructure.firebase_auth import get_current_user
from app.schemas.overtime import OvertimeCreate, OvertimeResponse

router = APIRouter(prefix='/api/budgets', tags=['overtime'])


def _get_entry(db: Session, budget_id: str, entry_id: str) -> OvertimeEntry:
    entry = db.execute(
        select(OvertimeEntry).where(OvertimeEntry.id == entry_id, OvertimeEntry.budget_id == budget_id)
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Overtime entry not found')
    return entry


@router.get('/{budget_id}/overtime', response_model=list[OvertimeResponse])
def list_overtime(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OvertimeEntry]:
    get_budget_for_user(db, budget_id, current_user)
    return db.execute(
        select(OvertimeEntry)
        .where(OvertimeEntry.budget_id == budget_id)
        .order_by(OvertimeEntry.date, OvertimeEntry.created_at)
    ).scalars().all()


@router.post('/{budget_id}/overtime', response_model=OvertimeResponse, status_code=status.HTTP_201_CREATED)
def create_overtime(
    budget_id: str,
    payload: OvertimeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OvertimeEntry:
    get_budget_for_user(db, budget_id, current_user)
    entry = OvertimeEntry(budget_id=budget_id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get('/{budget_id}/overtime/{entry_id}', response_model=OvertimeResponse)
def get_overtime(
    budget_id: str,
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OvertimeEntry:
    get_budget_for_user(db, budget_id, current_user)
    return _get_entry(db, budget_id, entry_id)


@router.put('/{budget_id}/overtime/{entry_id}', response_model=OvertimeResponse)
def update_overtime(
    budget_id: str,
    entry_id: str,
    payload: OvertimeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OvertimeEntry:
    get_budget_for_user(db, budget_id, current_user)
    entry = _get_entry(db, budget_id, entry_id)
    for key, value in payload.model_dump().items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete('/{budget_id}/overtime/{entry_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_overtime(
    budget_id: str,
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    get_budget_for_user(db, budget_id, current_user)
    entry = _get_entry(db, budget_id, entry_id)
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
