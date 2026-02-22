"""add etp fields to lots (fixed)

Revision ID: ac52df2fb2bc
Revises: 7dfc5094ad39
Create Date: 2026-02-22 04:53:49.912606

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ac52df2fb2bc'
down_revision = '7dfc5094ad39'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поля для ЭТП данных
    op.add_column('lots', sa.Column('etp_url', sa.Text(), nullable=True))
    op.add_column('lots', sa.Column('etp_name', sa.String(length=255), nullable=True))
    op.add_column('lots', sa.Column('application_start', sa.DateTime(timezone=True), nullable=True))
    op.add_column('lots', sa.Column('application_end', sa.DateTime(timezone=True), nullable=True))
    op.add_column('lots', sa.Column('organizer_name', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('lots', 'organizer_name')
    op.drop_column('lots', 'application_end')
    op.drop_column('lots', 'application_start')
    op.drop_column('lots', 'etp_name')
    op.drop_column('lots', 'etp_url')