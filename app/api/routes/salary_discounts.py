from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.dependencies import get_budget_for_user, get_db
from app.infrastructure.database.models.budget import Budget
from app.infrastructure.database.models.salary_discount import SalaryDiscount
from app.infrastructure.database.models.user import User
from app.infrastructure.firebase_auth import get_current_user
from app.schemas.salary_discount import SalaryDiscountCreate, SalaryDiscountResponse, SalaryDiscountUpdate

router = APIRouter(prefix='/api/budgets', tags=['salary-discounts'])


@router.get('/{budget_id}/discounts', response_model=list[SalaryDiscountResponse])
def list_salary_discounts(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SalaryDiscount]:
    get_budget_for_user(db, budget_id, current_user)
    discounts = db.execute(
        select(SalaryDiscount).where(SalaryDiscount.budget_id == budget_id).order_by(SalaryDiscount.created_at.desc())
    ).scalars().all()
    return discounts


@router.post('/{budget_id}/discounts', response_model=SalaryDiscountResponse, status_code=status.HTTP_201_CREATED)
def create_salary_discount(
    budget_id: str,
    payload: SalaryDiscountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SalaryDiscount:
    budget = get_budget_for_user(db, budget_id, current_user)
    discount = SalaryDiscount(
        budget_id=budget.id,
        name=payload.name,
        percentage=Decimal(str(payload.percentage)),
        enabled=payload.enabled,
    )
    db.add(discount)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Salary discount could not be created') from None
    db.refresh(discount)
    return discount


@router.get('/{budget_id}/discounts/{discount_id}', response_model=SalaryDiscountResponse)
def get_salary_discount(
    budget_id: str,
    discount_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SalaryDiscount:
    get_budget_for_user(db, budget_id, current_user)
    discount = db.execute(
        select(SalaryDiscount).where(SalaryDiscount.id == discount_id, SalaryDiscount.budget_id == budget_id)
    ).scalar_one_or_none()
    if discount is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Salary discount not found')
    return discount


@router.patch('/{budget_id}/discounts/{discount_id}', response_model=SalaryDiscountResponse)
def update_salary_discount(
    budget_id: str,
    discount_id: str,
    payload: SalaryDiscountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SalaryDiscount:
    get_budget_for_user(db, budget_id, current_user)
    discount = db.execute(
        select(SalaryDiscount).where(SalaryDiscount.id == discount_id, SalaryDiscount.budget_id == budget_id)
    ).scalar_one_or_none()
    if discount is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Salary discount not found')

    if payload.name is not None:
        discount.name = payload.name.strip()
    if payload.percentage is not None:
        discount.percentage = Decimal(str(payload.percentage))
    if payload.enabled is not None:
        discount.enabled = payload.enabled

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Salary discount could not be updated') from None

    db.refresh(discount)
    return discount


@router.delete('/{budget_id}/discounts/{discount_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_salary_discount(
    budget_id: str,
    discount_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    get_budget_for_user(db, budget_id, current_user)
    discount = db.execute(
        select(SalaryDiscount).where(SalaryDiscount.id == discount_id, SalaryDiscount.budget_id == budget_id)
    ).scalar_one_or_none()
    if discount is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Salary discount not found')

    db.delete(discount)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
