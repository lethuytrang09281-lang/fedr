"""add deal_score to lots

Revision ID: 8613b61acc8b
Revises: a881e873d6f2
Create Date: 2026-02-19 20:36:03.139358

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8613b61acc8b'
down_revision = 'a881e873d6f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('lots', sa.Column('deal_score', sa.Numeric(precision=5, scale=1), nullable=True))


def downgrade() -> None:
    op.drop_column('lots', 'deal_score')
