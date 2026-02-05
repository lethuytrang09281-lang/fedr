"""add rosreestr_address field

Revision ID: sprint2_address
Revises: sprint1_classification
Create Date: 2026-02-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'sprint2_address'
down_revision: Union[str, None] = 'sprint1_classification'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lots', sa.Column('rosreestr_address', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('lots', 'rosreestr_address')
