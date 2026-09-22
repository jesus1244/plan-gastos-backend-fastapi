from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OvertimeCreate(BaseModel):
    ordinary_day_hours: Decimal = Field(..., description='Ordinary day hours')
    ordinary_night_hours: Decimal = Field(..., description='Ordinary night hours')
    sunday_day_hours: Decimal = Field(..., description='Sunday day hours')
    sunday_night_hours: Decimal = Field(..., description='Sunday night hours')

    model_config = ConfigDict(extra='forbid')

    @field_validator('ordinary_day_hours', 'ordinary_night_hours', 'sunday_day_hours', 'sunday_night_hours')
    @classmethod
    def validate_hours(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError('hours must be greater than or equal to 0')
        return value.quantize(Decimal('0.01'))


class OvertimeResponse(BaseModel):
    budget_id: str
    ordinary_day_hours: Decimal
    ordinary_night_hours: Decimal
    sunday_day_hours: Decimal
    sunday_night_hours: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
