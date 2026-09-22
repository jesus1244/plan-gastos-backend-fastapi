from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.dependencies import get_budget_for_user, get_db
from app.infrastructure.database.models.budget import Budget
from app.infrastructure.database.models.income import Income
from app.infrastructure.database.models.user import User
from app.infrastructure.firebase_auth import get_current_user
from app.schemas.income import IncomeCreate, IncomeResponse, IncomeUpdate

router = APIRouter(prefix='/api/budgets', tags=['incomes'])


@router.get('/{budget_id}/incomes', response_model=list[IncomeResponse])
def list_incomes(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Income]:
    get_budget_for_user(db, budget_id, current_user)
    incomes = db.execute(
        select(Income).where(Income.budget_id == budget_id).order_by(Income.created_at.desc())
    ).scalars().all()
    return incomes


@router.post('/{budget_id}/incomes', response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
def create_income(
    budget_id: str,
    payload: IncomeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Income:
    budget = get_budget_for_user(db, budget_id, current_user)
    income = Income(
        budget_id=budget.id,
        name=payload.name,
        amount=Decimal(str(payload.amount)),
    )
    db.add(income)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Income could not be created') from None
    db.refresh(income)
    return income


@router.get('/{budget_id}/incomes/{income_id}', response_model=IncomeResponse)
def get_income(
    budget_id: str,
    income_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Income:
    get_budget_for_user(db, budget_id, current_user)
    income = db.execute(
        select(Income).where(Income.id == income_id, Income.budget_id == budget_id)
    ).scalar_one_or_none()
    if income is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Income not found')
    return income


@router.patch('/{budget_id}/incomes/{income_id}', response_model=IncomeResponse)
def update_income(
    budget_id: str,
    income_id: str,
    payload: IncomeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Income:
    get_budget_for_user(db, budget_id, current_user)
    income = db.execute(
        select(Income).where(Income.id == income_id, Income.budget_id == budget_id)
    ).scalar_one_or_none()
    if income is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Income not found')

    if payload.name is not None:
        income.name = payload.name.strip()
    if payload.amount is not None:
        income.amount = Decimal(str(payload.amount))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Income could not be updated') from None

    db.refresh(income)
    return income


@router.delete('/{budget_id}/incomes/{income_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_income(
    budget_id: str,
    income_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    get_budget_for_user(db, budget_id, current_user)
    income = db.execute(
        select(Income).where(Income.id == income_id, Income.budget_id == budget_id)
    ).scalar_one_or_none()
    if income is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Income not found')

    db.delete(income)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
