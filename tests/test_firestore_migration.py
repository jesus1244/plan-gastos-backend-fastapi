from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import Budget, Expense, Income, SalaryDiscount, User
from app.infrastructure.migration.migrator import FirestoreMigrator


def _clear_user(firebase_uid: str) -> None:
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one_or_none()
        if user is None:
            return
        for budget in list(user.budgets):
            session.delete(budget)
        session.delete(user)
        session.commit()


def _identity_resolver(directory: dict[str, tuple[str | None, str | None]]):
    def resolve(firebase_uid: str) -> tuple[str | None, str | None]:
        return directory.get(firebase_uid, (None, None))

    return resolve


def _run_migration(users_data: list[tuple[str, dict]], identity: dict[str, tuple[str | None, str | None]]):
    with SessionLocal() as session:
        migrator = FirestoreMigrator(
            session=session,
            fetch_users=lambda: list(users_data),
            resolve_identity=_identity_resolver(identity),
        )
        summary = migrator.run()
    return summary


def test_new_user_is_created_from_identity_resolver() -> None:
    uid = 'migration-test-new-user'
    _clear_user(uid)
    try:
        summary = _run_migration(
            [(uid, {'months': {}})],
            {uid: ('new.user@example.com', 'New User')},
        )

        assert summary.users_created == 1
        assert summary.users_reused == 0

        with SessionLocal() as session:
            user = session.execute(select(User).where(User.firebase_uid == uid)).scalar_one()
            assert user.email == 'new.user@example.com'
            assert user.display_name == 'New User'
    finally:
        _clear_user(uid)


def test_existing_user_is_reused_without_touching_identity() -> None:
    uid = 'migration-test-existing-user'
    _clear_user(uid)
    try:
        with SessionLocal() as session:
            session.add(User(firebase_uid=uid, email='original@example.com', display_name='Original'))
            session.commit()

        summary = _run_migration([(uid, {'months': {}})], {})

        assert summary.users_created == 0
        assert summary.users_reused == 1

        with SessionLocal() as session:
            user = session.execute(select(User).where(User.firebase_uid == uid)).scalar_one()
            assert user.email == 'original@example.com'
    finally:
        _clear_user(uid)


def test_user_without_resolvable_email_is_skipped_and_reported() -> None:
    uid = 'migration-test-missing-email'
    _clear_user(uid)
    try:
        summary = _run_migration([(uid, {'months': {}})], {})

        assert summary.users_created == 0
        assert summary.users_reused == 0
        assert any(issue.context == 'user' and issue.message == 'missing_email' for issue in summary.issues)

        with SessionLocal() as session:
            user = session.execute(select(User).where(User.firebase_uid == uid)).scalar_one_or_none()
            assert user is None
    finally:
        _clear_user(uid)


def test_generation2_month_migrates_budget_discounts_incomes_and_deduplicated_expenses() -> None:
    uid = 'migration-test-gen2-full'
    _clear_user(uid)
    try:
        month_data = {
            'id': '2026-09',
            'name': 'Septiembre 2026',
            'monthKey': '2026-09',
            'baseSalary': 3000000,
            'baseIncome': 3000000,
            'discounts': [
                {'id': 'd1', 'name': 'Salud', 'percentage': 4, 'enabled': True},
                {'id': 'd2', 'name': 'Pension', 'percentage': 4, 'enabled': True},
            ],
            'incomes': [{'id': 'income-1', 'name': 'Freelance', 'amount': 400000}],
            'extraIncome': [{'id': 'income-1', 'name': 'Freelance', 'amount': 400000}],
            'expenses': [
                {'id': 'expense-1', 'name': 'Arriendo', 'amount': 900000, 'type': 'fixed'},
                {'id': 'expense-2', 'name': 'Internet', 'amount': 80000, 'type': 'other'},
            ],
            'otherExpenses': [
                {'id': 'expense-1', 'name': 'Arriendo', 'amount': 900000, 'type': 'fixed'},
                {'id': 'expense-2', 'name': 'Internet', 'amount': 80000, 'type': 'other'},
            ],
        }

        summary = _run_migration(
            [(uid, {'months': {'2026-09': month_data}})],
            {uid: ('gen2@example.com', 'Gen2 User')},
        )

        assert summary.budgets_created == 1
        assert summary.discounts_migrated == 2
        assert summary.incomes_migrated == 1
        assert summary.expenses_migrated == 2
        assert summary.skipped_months == []

        with SessionLocal() as session:
            user = session.execute(select(User).where(User.firebase_uid == uid)).scalar_one()
            budget = session.execute(select(Budget).where(Budget.user_id == user.id, Budget.month_key == '2026-09')).scalar_one()
            assert budget.base_salary == Decimal('3000000.00') or budget.base_salary == Decimal('3000000')

            discounts = session.execute(select(SalaryDiscount).where(SalaryDiscount.budget_id == budget.id)).scalars().all()
            assert {d.name for d in discounts} == {'Salud', 'Pension'}

            incomes = session.execute(select(Income).where(Income.budget_id == budget.id)).scalars().all()
            assert len(incomes) == 1
            assert incomes[0].name == 'Freelance'

            expenses = session.execute(select(Expense).where(Expense.budget_id == budget.id)).scalars().all()
            assert {(e.name, e.type) for e in expenses} == {('Arriendo', 'fixed'), ('Internet', 'other')}

    finally:
        _clear_user(uid)


def test_generation1_month_without_monthkey_is_skipped_and_reported() -> None:
    uid = 'migration-test-gen1-skip'
    _clear_user(uid)
    try:
        month_data = {
            'name': 'Enero 2025',
            'baseIncome': 3000000,
            'extraIncome': [{'name': 'Bono', 'amount': 200000}],
            'expenses': [{'name': 'Arriendo', 'amount': 900000}],
            'otherExpenses': [{'name': 'Internet', 'amount': 80000}],
        }

        summary = _run_migration(
            [(uid, {'months': {'1737504000123': month_data}})],
            {uid: ('gen1@example.com', 'Gen1 User')},
        )

        assert summary.budgets_created == 0
        assert len(summary.skipped_months) == 1
        skipped = summary.skipped_months[0]
        assert skipped.firebase_uid == uid
        assert skipped.original_month_key == '1737504000123'
        assert skipped.name == 'Enero 2025'
        assert skipped.reason == 'missing_valid_month_key'

        with SessionLocal() as session:
            user = session.execute(select(User).where(User.firebase_uid == uid)).scalar_one()
            budgets = session.execute(select(Budget).where(Budget.user_id == user.id)).scalars().all()
            assert budgets == []
    finally:
        _clear_user(uid)


def test_generation1_month_with_valid_monthkey_migrates_fixed_and_other_expenses_no_discount() -> None:
    uid = 'migration-test-gen1-with-monthkey'
    _clear_user(uid)
    try:
        month_data = {
            'name': 'Enero 2025',
            'monthKey': '2025-01',
            'baseIncome': 3000000,
            'extraIncome': [{'name': 'Bono', 'amount': 200000}],
            'expenses': [{'name': 'Arriendo', 'amount': 900000}],
            'otherExpenses': [{'name': 'Internet', 'amount': 80000}],
            'overtime': {'days': {'5': {'diurnaOrd': 2, 'nocOrd': 1, 'diurnaDom': 0, 'nocDom': 0}}},
        }

        summary = _run_migration(
            [(uid, {'months': {'1737504000123': month_data}})],
            {uid: ('gen1valid@example.com', 'Gen1 Valid User')},
        )

        assert summary.budgets_created == 1
        assert summary.discounts_migrated == 0
        assert summary.incomes_migrated == 1
        assert summary.expenses_migrated == 2

        with SessionLocal() as session:
            user = session.execute(select(User).where(User.firebase_uid == uid)).scalar_one()
            budget = session.execute(select(Budget).where(Budget.user_id == user.id, Budget.month_key == '2025-01')).scalar_one()

            discounts = session.execute(select(SalaryDiscount).where(SalaryDiscount.budget_id == budget.id)).scalars().all()
            assert discounts == []

            expenses = session.execute(select(Expense).where(Expense.budget_id == budget.id)).scalars().all()
            assert {(e.name, e.type) for e in expenses} == {('Arriendo', 'fixed'), ('Internet', 'other')}

    finally:
        _clear_user(uid)


def test_month_with_valid_monthkey_but_missing_base_salary_is_skipped() -> None:
    uid = 'migration-test-missing-salary'
    _clear_user(uid)
    try:
        summary = _run_migration(
            [(uid, {'months': {'2026-10': {'name': 'Sin salario', 'monthKey': '2026-10'}}})],
            {uid: ('nosalary@example.com', None)},
        )

        assert summary.budgets_created == 0
        assert len(summary.skipped_months) == 1
        assert summary.skipped_months[0].reason == 'missing_base_salary'
    finally:
        _clear_user(uid)


def test_month_with_no_optional_arrays_creates_budget_without_children() -> None:
    uid = 'migration-test-empty-arrays'
    _clear_user(uid)
    try:
        summary = _run_migration(
            [(uid, {'months': {'2026-11': {'name': 'Mes vacío', 'monthKey': '2026-11', 'baseSalary': 1000000}}})],
            {uid: ('empty@example.com', None)},
        )

        assert summary.budgets_created == 1
        assert summary.discounts_migrated == 0
        assert summary.incomes_migrated == 0
        assert summary.expenses_migrated == 0
    finally:
        _clear_user(uid)


def test_invalid_income_entry_is_reported_but_does_not_block_valid_siblings() -> None:
    uid = 'migration-test-invalid-income'
    _clear_user(uid)
    try:
        month_data = {
            'name': 'Mes con datos invalidos',
            'monthKey': '2026-12',
            'baseSalary': 1500000,
            'incomes': [{'name': 'Bono'}, {'name': 'Extra', 'amount': 50000}],
        }

        summary = _run_migration(
            [(uid, {'months': {'2026-12': month_data}})],
            {uid: ('invalid@example.com', None)},
        )

        assert summary.budgets_created == 1
        assert summary.incomes_migrated == 1
        assert any(issue.message == 'income[0]: invalid_income_data' for issue in summary.issues)

        with SessionLocal() as session:
            user = session.execute(select(User).where(User.firebase_uid == uid)).scalar_one()
            budget = session.execute(select(Budget).where(Budget.user_id == user.id, Budget.month_key == '2026-12')).scalar_one()
            incomes = session.execute(select(Income).where(Income.budget_id == budget.id)).scalars().all()
            assert len(incomes) == 1
            assert incomes[0].name == 'Extra'
    finally:
        _clear_user(uid)


def test_running_migration_twice_is_idempotent() -> None:
    uid = 'migration-test-idempotent'
    _clear_user(uid)
    try:
        month_data = {
            'name': 'Septiembre 2026',
            'monthKey': '2026-09',
            'baseSalary': 3000000,
            'discounts': [{'name': 'Salud', 'percentage': 4, 'enabled': True}],
            'incomes': [{'name': 'Freelance', 'amount': 400000}],
            'expenses': [{'name': 'Arriendo', 'amount': 900000, 'type': 'fixed'}],
        }
        users_data = [(uid, {'months': {'2026-09': month_data}})]
        identity = {uid: ('idempotent@example.com', 'Idempotent User')}

        first = _run_migration(users_data, identity)
        second = _run_migration(users_data, identity)

        assert first.budgets_created == 1
        assert second.budgets_created == 0
        assert second.budgets_reused == 1
        assert second.users_reused == 1
        assert second.discounts_migrated == 0
        assert second.incomes_migrated == 0
        assert second.expenses_migrated == 0

        with SessionLocal() as session:
            user = session.execute(select(User).where(User.firebase_uid == uid)).scalar_one()
            budgets = session.execute(select(Budget).where(Budget.user_id == user.id)).scalars().all()
            assert len(budgets) == 1

            discounts = session.execute(select(SalaryDiscount).where(SalaryDiscount.budget_id == budgets[0].id)).scalars().all()
            assert len(discounts) == 1

            incomes = session.execute(select(Income).where(Income.budget_id == budgets[0].id)).scalars().all()
            assert len(incomes) == 1

            expenses = session.execute(select(Expense).where(Expense.budget_id == budgets[0].id)).scalars().all()
            assert len(expenses) == 1

    finally:
        _clear_user(uid)


def test_dry_run_does_not_persist_changes() -> None:
    uid = 'migration-test-dry-run'
    _clear_user(uid)
    try:
        month_data = {'name': 'Mes dry-run', 'monthKey': '2026-08', 'baseSalary': 2000000}

        with SessionLocal() as session:
            migrator = FirestoreMigrator(
                session=session,
                fetch_users=lambda: [(uid, {'months': {'2026-08': month_data}})],
                resolve_identity=_identity_resolver({uid: ('dryrun@example.com', None)}),
                dry_run=True,
            )
            summary = migrator.run()

        assert summary.users_created == 1
        assert summary.budgets_created == 1

        with SessionLocal() as session:
            user = session.execute(select(User).where(User.firebase_uid == uid)).scalar_one_or_none()
            assert user is None
    finally:
        _clear_user(uid)
