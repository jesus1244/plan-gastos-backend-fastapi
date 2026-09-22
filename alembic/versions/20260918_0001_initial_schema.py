"""Initial database schema

Revision ID: 20260918_0001
Revises: 
Create Date: 2026-09-18 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260918_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('firebase_uid', sa.String(length=128), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('firebase_uid', name='uq_users_firebase_uid'),
    )

    op.create_table(
        'budgets',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('month_key', sa.String(length=7), nullable=False),
        sa.Column('base_salary', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'month_key', name='uq_budgets_user_month'),
    )
    op.create_index(op.f('ix_budgets_user_id'), 'budgets', ['user_id'], unique=False)

    op.create_table(
        'salary_discounts',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('budget_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('percentage', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['budget_id'], ['budgets.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('percentage >= 0 AND percentage <= 100', name='ck_salary_discounts_percentage_range'),
    )
    op.create_index(op.f('ix_salary_discounts_budget_id'), 'salary_discounts', ['budget_id'], unique=False)

    op.create_table(
        'incomes',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('budget_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['budget_id'], ['budgets.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_incomes_budget_id'), 'incomes', ['budget_id'], unique=False)

    op.create_table(
        'expenses',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('budget_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['budget_id'], ['budgets.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("type IN ('fixed', 'other')", name='ck_expenses_type'),
    )
    op.create_index(op.f('ix_expenses_budget_id'), 'expenses', ['budget_id'], unique=False)

    op.create_table(
        'overtime',
        sa.Column('budget_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('ordinary_day_hours', sa.Numeric(precision=8, scale=2), nullable=False, server_default='0'),
        sa.Column('ordinary_night_hours', sa.Numeric(precision=8, scale=2), nullable=False, server_default='0'),
        sa.Column('sunday_day_hours', sa.Numeric(precision=8, scale=2), nullable=False, server_default='0'),
        sa.Column('sunday_night_hours', sa.Numeric(precision=8, scale=2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['budget_id'], ['budgets.id']),
        sa.PrimaryKeyConstraint('budget_id'),
        sa.CheckConstraint('ordinary_day_hours >= 0', name='ck_overtime_ordinary_day_hours_non_negative'),
        sa.CheckConstraint('ordinary_night_hours >= 0', name='ck_overtime_ordinary_night_hours_non_negative'),
        sa.CheckConstraint('sunday_day_hours >= 0', name='ck_overtime_sunday_day_hours_non_negative'),
        sa.CheckConstraint('sunday_night_hours >= 0', name='ck_overtime_sunday_night_hours_non_negative'),
    )


def downgrade() -> None:
    op.drop_table('overtime')
    op.drop_table('expenses')
    op.drop_table('incomes')
    op.drop_table('salary_discounts')
    op.drop_table('budgets')
    op.drop_table('users')
