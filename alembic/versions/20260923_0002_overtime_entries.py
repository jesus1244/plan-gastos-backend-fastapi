"""Replace aggregate overtime with detailed entries.

Revision ID: 20260923_0002
down_revision: 20260918_0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260923_0002'
down_revision = '20260918_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('overtime')
    op.create_table(
        'overtime_entries',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('budget_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('hours', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('shift', sa.String(length=20), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['budget_id'], ['budgets.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('hours > 0', name='ck_overtime_entries_hours_positive'),
        sa.CheckConstraint("type IN ('ordinary', 'sunday')", name='ck_overtime_entries_type'),
        sa.CheckConstraint("shift IN ('day', 'night')", name='ck_overtime_entries_shift'),
    )
    op.create_index('ix_overtime_entries_budget_id', 'overtime_entries', ['budget_id'], unique=False)
    op.create_index('ix_overtime_entries_date', 'overtime_entries', ['date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_overtime_entries_date', table_name='overtime_entries')
    op.drop_index('ix_overtime_entries_budget_id', table_name='overtime_entries')
    op.drop_table('overtime_entries')
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
    )
