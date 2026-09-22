from __future__ import annotations

from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models.budget import Budget
from app.infrastructure.database.models.user import User


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_budget_for_user(db: Session, budget_id: str, current_user: User) -> Budget:
    budget = db.execute(select(Budget).where(Budget.id == budget_id)).scalar_one_or_none()
    if budget is None or budget.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Budget not found')
    return budget