from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IncomeCreate(BaseModel):
    name: str = Field(..., min_length=1)
    amount: Decimal

    model_config = ConfigDict(extra='forbid')

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        if value is None or not value.strip():
            raise ValueError('name is required')
        return value.strip()

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError('amount must be greater than or equal to 0')
        return value.quantize(Decimal('0.01'))


class IncomeUpdate(BaseModel):
    name: str | None = None
    amount: Decimal | None = None

    model_config = ConfigDict(extra='forbid')

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError('name cannot be empty')
        if value is not None:
            return value.strip()
        return value

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return value
        if value < 0:
            raise ValueError('amount must be greater than or equal to 0')
        return value.quantize(Decimal('0.01'))


class IncomeResponse(BaseModel):
    id: str
    budget_id: str
    name: str
    amount: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
