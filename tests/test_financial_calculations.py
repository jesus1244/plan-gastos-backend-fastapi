from __future__ import annotations

from decimal import Decimal

from app.domain.financial_calculations import (
    OVERTIME_MULTIPLIERS,
    calculate_balance,
    calculate_base_hour_value,
    calculate_net_salary,
    calculate_overtime_income,
    calculate_total_expenses,
    calculate_total_income,
)


def test_net_salary_without_discounts() -> None:
    base = Decimal('3000000')
    assert calculate_net_salary(base, []) == Decimal('3000000.00')


def test_net_salary_with_enabled_discount() -> None:
    base = Decimal('3000000')
    discounts = [{'enabled': True, 'percentage': Decimal('8.00')}]
    assert calculate_net_salary(base, discounts) == Decimal('2760000.00')


def test_net_salary_ignores_disabled_discount() -> None:
    base = Decimal('3000000')
    discounts = [{'enabled': False, 'percentage': Decimal('8.00')}]
    assert calculate_net_salary(base, discounts) == Decimal('3000000.00')


def test_net_salary_sums_multiple_discounts() -> None:
    base = Decimal('3000000')
    discounts = [
        {'enabled': True, 'percentage': Decimal('8.00')},
        {'enabled': True, 'percentage': Decimal('5.00')},
    ]
    assert calculate_net_salary(base, discounts) == Decimal('2610000.00')


def test_base_hour_value_uses_decimal_precision() -> None:
    base = Decimal('3000000')
    assert calculate_base_hour_value(base) == Decimal('12500.00')


def test_overtime_ordinary_day_multiplier() -> None:
    result = calculate_overtime_income(Decimal('3000000'), {'ordinary_day_hours': Decimal('1.00')})
    expected = Decimal('3000000') / Decimal('240') * OVERTIME_MULTIPLIERS['ordinary_day']
    assert result == expected.quantize(Decimal('0.01'))
    assert OVERTIME_MULTIPLIERS['ordinary_day'] == Decimal('1.25')


def test_overtime_ordinary_night_multiplier() -> None:
    result = calculate_overtime_income(Decimal('3000000'), {'ordinary_night_hours': Decimal('1.00')})
    expected = Decimal('3000000') / Decimal('240') * OVERTIME_MULTIPLIERS['ordinary_night']
    assert result == expected.quantize(Decimal('0.01'))
    assert OVERTIME_MULTIPLIERS['ordinary_night'] == Decimal('1.75')


def test_overtime_sunday_day_multiplier() -> None:
    result = calculate_overtime_income(Decimal('3000000'), {'sunday_day_hours': Decimal('1.00')})
    expected = Decimal('3000000') / Decimal('240') * OVERTIME_MULTIPLIERS['sunday_day']
    assert result == expected.quantize(Decimal('0.01'))
    assert OVERTIME_MULTIPLIERS['sunday_day'] == Decimal('2.00')


def test_overtime_sunday_night_multiplier() -> None:
    result = calculate_overtime_income(Decimal('3000000'), {'sunday_night_hours': Decimal('1.00')})
    expected = Decimal('3000000') / Decimal('240') * OVERTIME_MULTIPLIERS['sunday_night']
    assert result == expected.quantize(Decimal('0.01'))
    assert OVERTIME_MULTIPLIERS['sunday_night'] == Decimal('2.50')


def test_overtime_combined_hours() -> None:
    result = calculate_overtime_income(
        Decimal('3000000'),
        {
            'ordinary_day_hours': Decimal('1.00'),
            'ordinary_night_hours': Decimal('1.00'),
            'sunday_day_hours': Decimal('1.00'),
            'sunday_night_hours': Decimal('1.00'),
        },
    )
    expected = (
        (Decimal('3000000') / Decimal('240'))
        * (
            OVERTIME_MULTIPLIERS['ordinary_day']
            + OVERTIME_MULTIPLIERS['ordinary_night']
            + OVERTIME_MULTIPLIERS['sunday_day']
            + OVERTIME_MULTIPLIERS['sunday_night']
        )
    )
    assert result == expected.quantize(Decimal('0.01'))


def test_total_income_combines_net_salary_incomes_and_overtime() -> None:
    total = calculate_total_income(Decimal('2760000'), [Decimal('100000'), Decimal('200000')], Decimal('50000'))
    assert total == Decimal('3110000.00')


def test_total_expenses_sums_fixed_and_other() -> None:
    total = calculate_total_expenses([Decimal('500000'), Decimal('200000'), Decimal('100000')])
    assert total == Decimal('800000.00')


def test_balance_uses_income_minus_expenses() -> None:
    assert calculate_balance(Decimal('3110000'), Decimal('800000')) == Decimal('2310000.00')
    assert calculate_balance(Decimal('500000'), Decimal('800000')) == Decimal('-300000.00')


def test_zero_and_empty_values() -> None:
    assert calculate_net_salary(Decimal('0'), []) == Decimal('0.00')
    assert calculate_total_income(Decimal('0'), [], Decimal('0')) == Decimal('0.00')
    assert calculate_total_expenses([]) == Decimal('0.00')
    assert calculate_balance(Decimal('0'), Decimal('0')) == Decimal('0.00')


def test_negative_values_are_rejected() -> None:
    try:
        calculate_net_salary(Decimal('-1'), [])
        raise AssertionError('Expected ValueError')
    except ValueError:
        pass

    try:
        calculate_total_income(Decimal('1000'), [Decimal('-1')], Decimal('0'))
        raise AssertionError('Expected ValueError')
    except ValueError:
        pass

    try:
        calculate_total_expenses([Decimal('-1')])
        raise AssertionError('Expected ValueError')
    except ValueError:
        pass

    try:
        calculate_overtime_income(Decimal('3000000'), {'ordinary_day_hours': Decimal('-1')})
        raise AssertionError('Expected ValueError')
    except ValueError:
        pass
