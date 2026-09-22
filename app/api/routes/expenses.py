from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.dependencies import get_budget_for_user, get_db
from app.infrastructure.database.models.budget import Budget
from app.infrastructure.database.models.expense import Expense
from app.infrastructure.database.models.user import User
from app.infrastructure.firebase_auth import get_current_user
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseUpdate

router = APIRouter(prefix='/api/budgets', tags=['expenses'])


@router.get('/{budget_id}/expenses', response_model=list[ExpenseResponse])
def list_expenses(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Expense]:
    get_budget_for_user(db, budget_id, current_user)
    expenses = db.execute(
        select(Expense).where(Expense.budget_id == budget_id).order_by(Expense.created_at.desc())
    ).scalars().all()
    return expenses


@router.post('/{budget_id}/expenses', response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    budget_id: str,
    payload: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Expense:
    budget = get_budget_for_user(db, budget_id, current_user)
    expense = Expense(
        budget_id=budget.id,
        name=payload.name,
        amount=Decimal(str(payload.amount)),
        type=payload.type.value,
    )
    db.add(expense)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Expense could not be created') from None
    db.refresh(expense)
    return expense


@router.get('/{budget_id}/expenses/{expense_id}', response_model=ExpenseResponse)
def get_expense(
    budget_id: str,
    expense_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Expense:
    get_budget_for_user(db, budget_id, current_user)
    expense = db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.budget_id == budget_id)
    ).scalar_one_or_none()
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Expense not found')
    return expense


@router.patch('/{budget_id}/expenses/{expense_id}', response_model=ExpenseResponse)
def update_expense(
    budget_id: str,
    expense_id: str,
    payload: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Expense:
    get_budget_for_user(db, budget_id, current_user)
    expense = db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.budget_id == budget_id)
    ).scalar_one_or_none()
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Expense not found')

    if payload.name is not None:
        expense.name = payload.name.strip()
    if payload.amount is not None:
        expense.amount = Decimal(str(payload.amount))
    if payload.type is not None:
        expense.type = payload.type.value

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Expense could not be updated') from None

    db.refresh(expense)
    return expense


@router.delete('/{budget_id}/expenses/{expense_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    budget_id: str,
    expense_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    get_budget_for_user(db, budget_id, current_user)
    expense = db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.budget_id == budget_id)
    ).scalar_one_or_none()
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Expense not found')

    db.delete(expense)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
