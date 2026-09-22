from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

MONTH_KEY_PATTERN = re.compile(r'^\d{4}-\d{2}$')


class BudgetCreate(BaseModel):
    name: str
    month_key: str
    base_salary: Decimal

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        if value is None or not value.strip():
            raise ValueError('name is required')
        return value.strip()

    @field_validator('month_key')
    @classmethod
    def validate_month_key(cls, value: str) -> str:
        if not MONTH_KEY_PATTERN.fullmatch(value):
            raise ValueError('month_key must use YYYY-MM format')

        year, month = value.split('-')
        month_number = int(month)
        if month_number < 1 or month_number > 12:
            raise ValueError('month_key must be a valid month in YYYY-MM format')
        return value

    @field_validator('base_salary')
    @classmethod
    def validate_base_salary(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError('base_salary must be greater than or equal to 0')
        return value.quantize(Decimal('0.01'))


class BudgetUpdate(BaseModel):
    name: str | None = None
    month_key: str | None = None
    base_salary: Decimal | None = None

    model_config = ConfigDict(extra='forbid')

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError('name cannot be empty')
        if value is not None:
            return value.strip()
        return value

    @field_validator('month_key')
    @classmethod
    def validate_month_key(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not MONTH_KEY_PATTERN.fullmatch(value):
            raise ValueError('month_key must use YYYY-MM format')
        year, month = value.split('-')
        month_number = int(month)
        if month_number < 1 or month_number > 12:
            raise ValueError('month_key must be a valid month in YYYY-MM format')
        return value

    @field_validator('base_salary')
    @classmethod
    def validate_base_salary(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return value
        if value < 0:
            raise ValueError('base_salary must be greater than or equal to 0')
        return value.quantize(Decimal('0.01'))


class BudgetResponse(BaseModel):
    id: str
    name: str
    month_key: str
    base_salary: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
