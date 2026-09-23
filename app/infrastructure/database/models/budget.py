from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.connection import Base


class Budget(Base):
    __tablename__ = 'budgets'
    __table_args__ = (
        UniqueConstraint('user_id', 'month_key', name='uq_budgets_user_month'),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey('users.id'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    month_key: Mapped[str] = mapped_column(String(7), nullable=False)
    base_salary: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship('User', backref='budgets')
    overtime_entries = relationship('OvertimeEntry', back_populates='budget', cascade='all, delete-orphan')
    salary_discounts = relationship('SalaryDiscount', back_populates='budget', cascade='all, delete-orphan')
    incomes = relationship('Income', back_populates='budget', cascade='all, delete-orphan')
    expenses = relationship('Expense', back_populates='budget', cascade='all, delete-orphan')
