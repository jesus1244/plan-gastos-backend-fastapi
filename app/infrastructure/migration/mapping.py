"""Pure, dependency-free mapping helpers for the Firestore -> PostgreSQL migration.

These functions only read from plain dict/list structures (as returned by the
Firestore Admin SDK's `document.to_dict()`) and never touch Firestore or
PostgreSQL. They encode the exact field names found in the two real schema
generations written by the legacy apps:

Generation 1 (legacy static HTML app, com.plan-gastos.app_web):
    users/{uid}.months[<Date.now() timestamp>] = {
        name: str,
        baseIncome: number,
        extraIncome: [{name, amount}],
        expenses: [{name, amount}],          # "Gastos Fijos" -> type fixed
        otherExpenses: [{name, amount}],      # "Otros Gastos" -> type other
        overtime: legacy Firestore data is intentionally not migrated to the new detailed model,
    }
    There is no persisted discount entity; the 8% is hardcoded in the client.

Generation 2 (current Angular app, plan_gastos_app):
    users/{uid}.months[<monthKey>] = {
        name: str,
        monthKey: "YYYY-MM",
        baseSalary / baseIncome: number,
        discounts: [{id, name, percentage, enabled}],
        incomes / extraIncome: [{id, name, amount}],
        expenses: [{id, name, amount, type: 'fixed' | 'other'}],
        otherExpenses: same array as `expenses` (mirrored on write),
        overtime: legacy aggregate data is intentionally not migrated to the new detailed model,
    }
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

MONTH_KEY_PATTERN = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')


@dataclass
class ParsedExpense:
    name: str
    amount: Decimal
    type: str


@dataclass
class ParsedIncome:
    name: str
    amount: Decimal


@dataclass
class ParsedDiscount:
    name: str
    percentage: Decimal
    enabled: bool


@dataclass
@dataclass
class ParsedMonth:
    month_key: str
    name: str
    base_salary: Decimal
    discounts: list[ParsedDiscount] = field(default_factory=list)
    incomes: list[ParsedIncome] = field(default_factory=list)
    expenses: list[ParsedExpense] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def to_decimal(value: object) -> Decimal | None:
    """Convert a Firestore scalar into a non-negative Decimal, or None if unsafe."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            result = Decimal(str(value))
        except (ValueError, ArithmeticError):
            return None
    elif isinstance(value, str) and value.strip():
        try:
            result = Decimal(value.strip())
        except (ValueError, ArithmeticError):
            return None
    else:
        return None

    if result < 0:
        return None
    return result


def is_valid_month_key(value: object) -> bool:
    return isinstance(value, str) and bool(MONTH_KEY_PATTERN.match(value.strip()))


def extract_months(user_data: dict) -> dict[str, dict]:
    months = user_data.get('months')
    if not isinstance(months, dict):
        return {}
    return {key: value for key, value in months.items() if isinstance(value, dict)}


def extract_valid_month_key(month_data: dict) -> str | None:
    raw = month_data.get('monthKey')
    if is_valid_month_key(raw):
        return raw.strip()  # type: ignore[union-attr]
    return None


def extract_base_salary(month_data: dict) -> tuple[Decimal | None, str | None]:
    raw = month_data['baseSalary'] if 'baseSalary' in month_data else month_data.get('baseIncome')
    if raw is None:
        return None, 'missing_base_salary'
    value = to_decimal(raw)
    if value is None:
        return None, 'invalid_base_salary'
    return value, None


def extract_discounts(month_data: dict) -> tuple[list[ParsedDiscount], list[str]]:
    raw = month_data.get('discounts')
    if not isinstance(raw, list):
        return [], []

    results: list[ParsedDiscount] = []
    issues: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            issues.append(f'discount[{index}]: invalid_entry')
            continue

        name = item.get('name')
        percentage = to_decimal(item.get('percentage'))
        if not isinstance(name, str) or not name.strip() or percentage is None or percentage > 100:
            issues.append(f'discount[{index}]: invalid_discount_data')
            continue

        results.append(ParsedDiscount(name=name.strip(), percentage=percentage, enabled=bool(item.get('enabled', False))))

    return results, issues


def extract_incomes(month_data: dict) -> tuple[list[ParsedIncome], list[str]]:
    raw = month_data['incomes'] if 'incomes' in month_data else month_data.get('extraIncome')
    if not isinstance(raw, list):
        return [], []

    results: list[ParsedIncome] = []
    issues: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            issues.append(f'income[{index}]: invalid_entry')
            continue

        name = item.get('name')
        amount = to_decimal(item.get('amount'))
        if not isinstance(name, str) or not name.strip() or amount is None:
            issues.append(f'income[{index}]: invalid_income_data')
            continue

        results.append(ParsedIncome(name=name.strip(), amount=amount))

    return results, issues


def _parse_expense_entry(item: object, forced_type: str | None) -> tuple[ParsedExpense | None, str | None]:
    if not isinstance(item, dict):
        return None, 'invalid_entry'

    name = item.get('name')
    amount = to_decimal(item.get('amount'))
    if not isinstance(name, str) or not name.strip() or amount is None:
        return None, 'invalid_expense_data'

    if forced_type is not None:
        expense_type = forced_type
    else:
        expense_type = item.get('type') if item.get('type') in ('fixed', 'other') else 'fixed'

    return ParsedExpense(name=name.strip(), amount=amount, type=expense_type), None


def extract_expenses(month_data: dict) -> tuple[list[ParsedExpense], list[str]]:
    expenses_raw = month_data.get('expenses')
    other_raw = month_data.get('otherExpenses')
    expenses_list = expenses_raw if isinstance(expenses_raw, list) else []
    other_list = other_raw if isinstance(other_raw, list) else []

    results: list[ParsedExpense] = []
    issues: list[str] = []

    is_generation_2 = any(isinstance(item, dict) and 'type' in item for item in expenses_list)

    if is_generation_2:
        # `otherExpenses` mirrors `expenses` on write in the current Angular schema; reading
        # both would double-count every record, so only `expenses` (with its own type) is used.
        for index, item in enumerate(expenses_list):
            parsed, issue = _parse_expense_entry(item, forced_type=None)
            if issue is not None:
                issues.append(f'expense[{index}]: {issue}')
                continue
            results.append(parsed)  # type: ignore[arg-type]
        return results, issues

    for index, item in enumerate(expenses_list):
        parsed, issue = _parse_expense_entry(item, forced_type='fixed')
        if issue is not None:
            issues.append(f'expense[{index}]: {issue}')
            continue
        results.append(parsed)  # type: ignore[arg-type]

    for index, item in enumerate(other_list):
        parsed, issue = _parse_expense_entry(item, forced_type='other')
        if issue is not None:
            issues.append(f'otherExpense[{index}]: {issue}')
            continue
        results.append(parsed)  # type: ignore[arg-type]

    return results, issues


def extract_month_name(month_data: dict, fallback: str) -> str:
    raw_name = month_data.get('name')
    return raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else fallback


def parse_month(month_data: dict) -> ParsedMonth | None:
    """Parse a valid, migratable Firestore month document.

    Callers must first ensure `extract_valid_month_key` succeeds and
    `extract_base_salary` returns a value; this function does not decide
    whether a month should be skipped.
    """
    month_key = extract_valid_month_key(month_data)
    base_salary, _ = extract_base_salary(month_data)
    if month_key is None or base_salary is None:
        return None

    discounts, discount_issues = extract_discounts(month_data)
    incomes, income_issues = extract_incomes(month_data)
    expenses, expense_issues = extract_expenses(month_data)

    return ParsedMonth(
        month_key=month_key,
        name=extract_month_name(month_data, fallback=month_key),
        base_salary=base_salary,
        discounts=discounts,
        incomes=incomes,
        expenses=expenses,
        issues=[*discount_issues, *income_issues, *expense_issues],
    )
