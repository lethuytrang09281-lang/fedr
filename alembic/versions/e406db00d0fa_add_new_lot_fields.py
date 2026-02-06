"""Add new lot fields

Revision ID: e406db00d0fa
Revises:
Create Date: 2026-02-06 08:30:46.752941

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e406db00d0fa'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to lots table
    op.add_column('lots', sa.Column('is_relevant', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('lots', sa.Column('location_zone', sa.String(length=50), nullable=True))
    op.add_column('lots', sa.Column('semantic_tags', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False))
    op.add_column('lots', sa.Column('red_flags', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False))

    op.add_column('lots', sa.Column('rosreestr_area', sa.Numeric(precision=15, scale=2), nullable=True))
    op.add_column('lots', sa.Column('rosreestr_value', sa.Numeric(precision=20, scale=2), nullable=True))
    op.add_column('lots', sa.Column('rosreestr_vri', sa.String(length=500), nullable=True))
    op.add_column('lots', sa.Column('rosreestr_address', sa.Text(), nullable=True))
    op.add_column('lots', sa.Column('needs_enrichment', sa.Boolean(), nullable=False, server_default='true'))

    # Create index for needs_enrichment
    op.create_index('ix_lots_needs_enrichment', 'lots', ['needs_enrichment'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_lots_needs_enrichment', table_name='lots')
    op.drop_column('lots', 'needs_enrichment')
    op.drop_column('lots', 'rosreestr_address')
    op.drop_column('lots', 'rosreestr_vri')
    op.drop_column('lots', 'rosreestr_value')
    op.drop_column('lots', 'rosreestr_area')
    op.drop_column('lots', 'red_flags')
    op.drop_column('lots', 'semantic_tags')
    op.drop_column('lots', 'location_zone')
    op.drop_column('lots', 'is_relevant')
