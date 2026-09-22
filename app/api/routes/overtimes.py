from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.dependencies import get_budget_for_user, get_db
from app.infrastructure.database.models.budget import Budget
from app.infrastructure.database.models.overtime import Overtime
from app.infrastructure.database.models.user import User
from app.infrastructure.firebase_auth import get_current_user
from app.schemas.overtime import OvertimeCreate, OvertimeResponse

router = APIRouter(prefix='/api/budgets', tags=['overtime'])


@router.get('/{budget_id}/overtime', response_model=OvertimeResponse)
def get_overtime(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Overtime:
    get_budget_for_user(db, budget_id, current_user)
    overtime = db.execute(select(Overtime).where(Overtime.budget_id == budget_id)).scalar_one_or_none()
    if overtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Overtime not found')
    return overtime


@router.put('/{budget_id}/overtime', response_model=OvertimeResponse)
def upsert_overtime(
    budget_id: str,
    payload: OvertimeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Overtime:
    budget = get_budget_for_user(db, budget_id, current_user)
    overtime = db.execute(select(Overtime).where(Overtime.budget_id == budget_id)).scalar_one_or_none()

    if overtime is None:
        overtime = Overtime(
            budget_id=budget.id,
            ordinary_day_hours=Decimal(str(payload.ordinary_day_hours)),
            ordinary_night_hours=Decimal(str(payload.ordinary_night_hours)),
            sunday_day_hours=Decimal(str(payload.sunday_day_hours)),
            sunday_night_hours=Decimal(str(payload.sunday_night_hours)),
        )
        db.add(overtime)
    else:
        overtime.ordinary_day_hours = Decimal(str(payload.ordinary_day_hours))
        overtime.ordinary_night_hours = Decimal(str(payload.ordinary_night_hours))
        overtime.sunday_day_hours = Decimal(str(payload.sunday_day_hours))
        overtime.sunday_night_hours = Decimal(str(payload.sunday_night_hours))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Overtime could not be saved') from None

    db.refresh(overtime)
    return overtime


@router.delete('/{budget_id}/overtime', status_code=status.HTTP_204_NO_CONTENT)
def delete_overtime(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    get_budget_for_user(db, budget_id, current_user)
    overtime = db.execute(select(Overtime).where(Overtime.budget_id == budget_id)).scalar_one_or_none()
    if overtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Overtime not found')

    db.delete(overtime)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
