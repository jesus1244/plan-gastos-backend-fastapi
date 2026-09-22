from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANT = Decimal('0.01')
OVERTIME_MULTIPLIERS = {
    'ordinary_day': Decimal('1.25'),
    'ordinary_night': Decimal('1.75'),
    'sunday_day': Decimal('2.00'),
    'sunday_night': Decimal('2.50'),
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def calculate_net_salary(base_salary: Decimal, discounts: list[dict[str, object]] | list[object] | None) -> Decimal:
    base_salary = _money(base_salary)
    if base_salary < 0:
        raise ValueError('base_salary cannot be negative')

    if not discounts:
        return base_salary

    total_discount = Decimal('0')
    for discount in discounts:
        if discount is None:
            continue
        if isinstance(discount, dict):
            enabled = discount.get('enabled', False)
            percentage = discount.get('percentage', Decimal('0'))
            if enabled:
                if percentage < 0:
                    raise ValueError('discount percentage cannot be negative')
                total_discount += (base_salary * Decimal(str(percentage))) / Decimal('100')
        else:
            enabled = getattr(discount, 'enabled', False)
            percentage = getattr(discount, 'percentage', Decimal('0'))
            if enabled:
                if percentage < 0:
                    raise ValueError('discount percentage cannot be negative')
                total_discount += (base_salary * Decimal(str(percentage))) / Decimal('100')

    return _money(base_salary - total_discount)


def calculate_base_hour_value(base_salary: Decimal) -> Decimal:
    base_salary = _money(base_salary)
    if base_salary < 0:
        raise ValueError('base_salary cannot be negative')
    return _money(base_salary / Decimal('240'))


def calculate_overtime_income(base_salary: Decimal, overtime_hours: dict[str, Decimal | int | float]) -> Decimal:
    base_salary = _money(base_salary)
    if base_salary < 0:
        raise ValueError('base_salary cannot be negative')

    base_hour_value = base_salary / Decimal('240')
    ordinary_day = Decimal(str(overtime_hours.get('ordinary_day_hours', 0)))
    ordinary_night = Decimal(str(overtime_hours.get('ordinary_night_hours', 0)))
    sunday_day = Decimal(str(overtime_hours.get('sunday_day_hours', 0)))
    sunday_night = Decimal(str(overtime_hours.get('sunday_night_hours', 0)))

    if ordinary_day < 0 or ordinary_night < 0 or sunday_day < 0 or sunday_night < 0:
        raise ValueError('overtime hours cannot be negative')

    total = (
        (ordinary_day * base_hour_value * OVERTIME_MULTIPLIERS['ordinary_day'])
        + (ordinary_night * base_hour_value * OVERTIME_MULTIPLIERS['ordinary_night'])
        + (sunday_day * base_hour_value * OVERTIME_MULTIPLIERS['sunday_day'])
        + (sunday_night * base_hour_value * OVERTIME_MULTIPLIERS['sunday_night'])
    )
    return _money(total)


def calculate_total_income(net_salary: Decimal, incomes: list[Decimal | int | float], overtime_income: Decimal) -> Decimal:
    total = Decimal(str(net_salary))
    for income in incomes:
        value = Decimal(str(income))
        if value < 0:
            raise ValueError('income amount cannot be negative')
        total += value
    total += Decimal(str(overtime_income))
    return _money(total)


def calculate_total_expenses(expenses: list[Decimal | int | float]) -> Decimal:
    total = Decimal('0')
    for expense in expenses:
        value = Decimal(str(expense))
        if value < 0:
            raise ValueError('expense amount cannot be negative')
        total += value
    return _money(total)


def calculate_balance(total_income: Decimal, total_expenses: Decimal) -> Decimal:
    return _money(Decimal(str(total_income)) - Decimal(str(total_expenses)))
