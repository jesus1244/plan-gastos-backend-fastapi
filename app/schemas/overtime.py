from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OvertimeType = Literal['ordinary', 'sunday']
OvertimeShift = Literal['day', 'night']


class OvertimeCreate(BaseModel):
    date: date
    hours: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    type: OvertimeType
    shift: OvertimeShift
    start_time: time | None = None
    end_time: time | None = None
    description: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(extra='forbid')

    @model_validator(mode='after')
    def validate_time_pair(self) -> 'OvertimeCreate':
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError('start_time and end_time must be provided together')
        return self

    @model_validator(mode='after')
    def normalize_description(self) -> 'OvertimeCreate':
        if self.description is not None:
            self.description = self.description.strip() or None
        return self


class OvertimeResponse(OvertimeCreate):
    id: str
    budget_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
