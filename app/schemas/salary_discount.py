from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SalaryDiscountCreate(BaseModel):
    name: str
    percentage: Decimal
    enabled: bool = True

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        if value is None or not value.strip():
            raise ValueError('name is required')
        return value.strip()

    @field_validator('percentage')
    @classmethod
    def validate_percentage(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError('percentage must be greater than or equal to 0')
        if value > Decimal('100'):
            raise ValueError('percentage must be less than or equal to 100')
        return value.quantize(Decimal('0.01'))


class SalaryDiscountUpdate(BaseModel):
    name: str | None = None
    percentage: Decimal | None = None
    enabled: bool | None = None

    model_config = ConfigDict(extra='forbid')

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError('name cannot be empty')
        if value is not None:
            return value.strip()
        return value

    @field_validator('percentage')
    @classmethod
    def validate_percentage(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return value
        if value < 0:
            raise ValueError('percentage must be greater than or equal to 0')
        if value > Decimal('100'):
            raise ValueError('percentage must be less than or equal to 100')
        return value.quantize(Decimal('0.01'))


class SalaryDiscountResponse(BaseModel):
    id: str
    budget_id: str
    name: str
    percentage: Decimal
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
