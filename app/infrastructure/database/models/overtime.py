from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.connection import Base


class OvertimeEntry(Base):
    __tablename__ = 'overtime_entries'
    __table_args__ = (
        CheckConstraint('hours > 0', name='ck_overtime_entries_hours_positive'),
        CheckConstraint("type IN ('ordinary', 'sunday')", name='ck_overtime_entries_type'),
        CheckConstraint("shift IN ('day', 'night')", name='ck_overtime_entries_shift'),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    budget_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey('budgets.id'), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    shift: Mapped[str] = mapped_column(String(20), nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    budget = relationship('Budget', back_populates='overtime_entries')
