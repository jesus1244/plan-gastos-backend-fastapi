from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.dependencies import get_db
from app.infrastructure.database.models.budget import Budget
from app.infrastructure.database.models.user import User
from app.infrastructure.firebase_auth import get_current_user
from app.schemas.budget import BudgetCreate, BudgetResponse, BudgetUpdate

router = APIRouter(prefix='/api/budgets', tags=['budgets'])


@router.get('', response_model=list[BudgetResponse])
def list_budgets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Budget]:
    budgets = db.execute(
        select(Budget).where(Budget.user_id == current_user.id).order_by(Budget.created_at.desc())
    ).scalars().all()
    return budgets


@router.get('/{budget_id}', response_model=BudgetResponse)
def get_budget(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Budget:
    budget = db.execute(select(Budget).where(Budget.id == budget_id)).scalar_one_or_none()
    if budget is None or budget.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Budget not found')
    return budget


@router.post('', response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Budget:
    budget = Budget(
        user_id=current_user.id,
        name=payload.name,
        month_key=payload.month_key,
        base_salary=Decimal(str(payload.base_salary)),
    )
    db.add(budget)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Budget for this month already exists') from None
    db.refresh(budget)
    return budget


@router.patch('/{budget_id}', response_model=BudgetResponse)
def update_budget(
    budget_id: str,
    payload: BudgetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Budget:
    budget = db.execute(select(Budget).where(Budget.id == budget_id)).scalar_one_or_none()
    if budget is None or budget.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Budget not found')

    if payload.name is not None:
        budget.name = payload.name.strip()
    if payload.month_key is not None:
        budget.month_key = payload.month_key
    if payload.base_salary is not None:
        budget.base_salary = Decimal(str(payload.base_salary))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Budget for this month already exists') from None

    db.refresh(budget)
    return budget


@router.delete('/{budget_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    budget = db.execute(select(Budget).where(Budget.id == budget_id)).scalar_one_or_none()
    if budget is None or budget.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Budget not found')

    db.delete(budget)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
