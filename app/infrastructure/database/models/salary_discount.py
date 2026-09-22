from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.connection import Base


class SalaryDiscount(Base):
    __tablename__ = 'salary_discounts'
    __table_args__ = (
        CheckConstraint('percentage >= 0 AND percentage <= 100', name='ck_salary_discounts_percentage_range'),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    budget_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey('budgets.id'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    budget = relationship('Budget', back_populates='salary_discounts')
