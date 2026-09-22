"""Idempotent orchestration of the Firestore -> PostgreSQL migration (Fase 21).

Firestore access is injected as plain callables so this module never imports
firebase_admin directly and can be fully unit tested without a real project.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.budget import Budget
from app.infrastructure.database.models.expense import Expense
from app.infrastructure.database.models.income import Income
from app.infrastructure.database.models.overtime import Overtime
from app.infrastructure.database.models.salary_discount import SalaryDiscount
from app.infrastructure.database.models.user import User
from app.infrastructure.migration.mapping import (
    ParsedMonth,
    extract_base_salary,
    extract_months,
    extract_valid_month_key,
    parse_month,
)

FetchUsers = Callable[[], Iterable[tuple[str, dict]]]
ResolveIdentity = Callable[[str], tuple[str | None, str | None]]


@dataclass
class SkippedMonth:
    firebase_uid: str
    original_month_key: str
    name: str | None
    reason: str


@dataclass
class MigrationIssue:
    firebase_uid: str
    context: str
    message: str


@dataclass
class MigrationSummary:
    users_processed: int = 0
    users_created: int = 0
    users_reused: int = 0
    budgets_created: int = 0
    budgets_reused: int = 0
    discounts_migrated: int = 0
    incomes_migrated: int = 0
    expenses_migrated: int = 0
    overtime_migrated: int = 0
    skipped_months: list[SkippedMonth] = field(default_factory=list)
    issues: list[MigrationIssue] = field(default_factory=list)

    def report(self, dry_run: bool = False) -> str:
        lines = [
            f'Firestore -> PostgreSQL migration {"(dry-run, no changes written)" if dry_run else "(applied)"}',
            f'  users processed:      {self.users_processed}',
            f'  users created:        {self.users_created}',
            f'  users reused:         {self.users_reused}',
            f'  budgets created:      {self.budgets_created}',
            f'  budgets reused:       {self.budgets_reused}',
            f'  discounts migrated:   {self.discounts_migrated}',
            f'  incomes migrated:     {self.incomes_migrated}',
            f'  expenses migrated:    {self.expenses_migrated}',
            f'  overtime migrated:    {self.overtime_migrated}',
            f'  months skipped:       {len(self.skipped_months)}',
            f'  errors:               {len(self.issues)}',
        ]
        for skipped in self.skipped_months:
            lines.append(
                f'    SKIPPED user={skipped.firebase_uid} month_key={skipped.original_month_key!r} '
                f'name={skipped.name!r} reason={skipped.reason}'
            )
        for issue in self.issues:
            lines.append(f'    ISSUE user={issue.firebase_uid} context={issue.context} message={issue.message}')
        return '\n'.join(lines)


class FirestoreMigrator:
    def __init__(
        self,
        session: Session,
        fetch_users: FetchUsers,
        resolve_identity: ResolveIdentity,
        dry_run: bool = False,
    ) -> None:
        self._session = session
        self._fetch_users = fetch_users
        self._resolve_identity = resolve_identity
        self._dry_run = dry_run

    def run(self) -> MigrationSummary:
        summary = MigrationSummary()

        for firebase_uid, user_data in self._fetch_users():
            summary.users_processed += 1

            if not isinstance(user_data, dict):
                summary.issues.append(MigrationIssue(firebase_uid, 'user', 'invalid_user_document'))
                continue

            user = self._get_or_create_user(firebase_uid, summary)
            if user is None:
                continue

            for source_month_key, month_data in extract_months(user_data).items():
                self._migrate_month(user, firebase_uid, source_month_key, month_data, summary)

        if self._dry_run:
            self._session.rollback()
        else:
            self._session.commit()

        return summary

    def _get_or_create_user(self, firebase_uid: str, summary: MigrationSummary) -> User | None:
        existing = self._session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one_or_none()
        if existing is not None:
            summary.users_reused += 1
            return existing

        email, display_name = self._resolve_identity(firebase_uid)
        if not email:
            summary.issues.append(MigrationIssue(firebase_uid, 'user', 'missing_email'))
            return None

        user = User(firebase_uid=firebase_uid, email=email, display_name=display_name)
        self._session.add(user)
        self._session.flush()
        summary.users_created += 1
        return user

    def _migrate_month(
        self,
        user: User,
        firebase_uid: str,
        source_month_key: str,
        month_data: dict,
        summary: MigrationSummary,
    ) -> None:
        raw_name = month_data.get('name') if isinstance(month_data.get('name'), str) else None

        month_key = extract_valid_month_key(month_data)
        if month_key is None:
            summary.skipped_months.append(SkippedMonth(firebase_uid, source_month_key, raw_name, 'missing_valid_month_key'))
            return

        base_salary, base_salary_issue = extract_base_salary(month_data)
        if base_salary is None:
            summary.skipped_months.append(
                SkippedMonth(firebase_uid, source_month_key, raw_name, base_salary_issue or 'missing_base_salary')
            )
            return

        parsed = parse_month(month_data)
        assert parsed is not None  # month_key and base_salary were already validated above

        for issue in parsed.issues:
            summary.issues.append(MigrationIssue(firebase_uid, f'{month_key}', issue))

        budget, created = self._get_or_create_budget(user, parsed)
        summary.budgets_created += int(created)
        summary.budgets_reused += int(not created)

        summary.discounts_migrated += self._migrate_discounts(budget, parsed)
        summary.incomes_migrated += self._migrate_incomes(budget, parsed)
        summary.expenses_migrated += self._migrate_expenses(budget, parsed)
        summary.overtime_migrated += self._migrate_overtime(budget, parsed)

    def _get_or_create_budget(self, user: User, parsed: ParsedMonth) -> tuple[Budget, bool]:
        existing = self._session.execute(
            select(Budget).where(Budget.user_id == user.id, Budget.month_key == parsed.month_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False

        budget = Budget(user_id=user.id, name=parsed.name, month_key=parsed.month_key, base_salary=parsed.base_salary)
        self._session.add(budget)
        self._session.flush()
        return budget, True

    def _migrate_discounts(self, budget: Budget, parsed: ParsedMonth) -> int:
        migrated = 0
        for discount in parsed.discounts:
            existing = self._session.execute(
                select(SalaryDiscount).where(SalaryDiscount.budget_id == budget.id, SalaryDiscount.name == discount.name)
            ).scalar_one_or_none()
            if existing is not None:
                continue
            self._session.add(
                SalaryDiscount(budget_id=budget.id, name=discount.name, percentage=discount.percentage, enabled=discount.enabled)
            )
            migrated += 1
        if migrated:
            self._session.flush()
        return migrated

    def _migrate_incomes(self, budget: Budget, parsed: ParsedMonth) -> int:
        migrated = 0
        for income in parsed.incomes:
            existing = self._session.execute(
                select(Income).where(Income.budget_id == budget.id, Income.name == income.name, Income.amount == income.amount)
            ).scalar_one_or_none()
            if existing is not None:
                continue
            self._session.add(Income(budget_id=budget.id, name=income.name, amount=income.amount))
            migrated += 1
        if migrated:
            self._session.flush()
        return migrated

    def _migrate_expenses(self, budget: Budget, parsed: ParsedMonth) -> int:
        migrated = 0
        for expense in parsed.expenses:
            existing = self._session.execute(
                select(Expense).where(
                    Expense.budget_id == budget.id,
                    Expense.name == expense.name,
                    Expense.amount == expense.amount,
                    Expense.type == expense.type,
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue
            self._session.add(Expense(budget_id=budget.id, name=expense.name, amount=expense.amount, type=expense.type))
            migrated += 1
        if migrated:
            self._session.flush()
        return migrated

    def _migrate_overtime(self, budget: Budget, parsed: ParsedMonth) -> int:
        if parsed.overtime is None:
            return 0

        existing = self._session.execute(select(Overtime).where(Overtime.budget_id == budget.id)).scalar_one_or_none()
        if existing is not None:
            existing.ordinary_day_hours = parsed.overtime.ordinary_day_hours
            existing.ordinary_night_hours = parsed.overtime.ordinary_night_hours
            existing.sunday_day_hours = parsed.overtime.sunday_day_hours
            existing.sunday_night_hours = parsed.overtime.sunday_night_hours
        else:
            self._session.add(
                Overtime(
                    budget_id=budget.id,
                    ordinary_day_hours=parsed.overtime.ordinary_day_hours,
                    ordinary_night_hours=parsed.overtime.ordinary_night_hours,
                    sunday_day_hours=parsed.overtime.sunday_day_hours,
                    sunday_night_hours=parsed.overtime.sunday_night_hours,
                )
            )
        self._session.flush()
        return 1
