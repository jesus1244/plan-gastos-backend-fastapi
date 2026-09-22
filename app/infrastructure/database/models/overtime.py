from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.connection import Base


class Overtime(Base):
    __tablename__ = 'overtime'
    __table_args__ = (
        CheckConstraint('ordinary_day_hours >= 0', name='ck_overtime_ordinary_day_hours_non_negative'),
        CheckConstraint('ordinary_night_hours >= 0', name='ck_overtime_ordinary_night_hours_non_negative'),
        CheckConstraint('sunday_day_hours >= 0', name='ck_overtime_sunday_day_hours_non_negative'),
        CheckConstraint('sunday_night_hours >= 0', name='ck_overtime_sunday_night_hours_non_negative'),
    )

    budget_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey('budgets.id'), primary_key=True)
    ordinary_day_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    ordinary_night_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    sunday_day_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    sunday_night_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    budget = relationship('Budget', back_populates='overtime')
