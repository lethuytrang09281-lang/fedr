"""add leads table

Revision ID: a2f4c8e91b30
Revises: 661f17671023
Create Date: 2026-02-21 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a2f4c8e91b30'
down_revision = '661f17671023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'leads',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('debtor_guid', sa.String(length=100), nullable=True),
        sa.Column('debtor_name', sa.Text(), nullable=True),
        sa.Column('debtor_inn', sa.String(length=12), nullable=True),
        sa.Column('message_type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('estimated_value', sa.Integer(), nullable=True),
        sa.Column('source_message_id', sa.String(length=100), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='new'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_message_id', name='leads_source_message_id_key'),
    )
    op.create_index('ix_leads_debtor_guid', 'leads', ['debtor_guid'])
    op.create_index('ix_leads_source_message_id', 'leads', ['source_message_id'])
    op.create_index('ix_leads_status', 'leads', ['status'])


def downgrade() -> None:
    op.drop_index('ix_leads_status', table_name='leads')
    op.drop_index('ix_leads_source_message_id', table_name='leads')
    op.drop_index('ix_leads_debtor_guid', table_name='leads')
    op.drop_table('leads')
