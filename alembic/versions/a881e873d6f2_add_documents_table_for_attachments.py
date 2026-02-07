"""add_documents_table_for_attachments

Revision ID: a881e873d6f2
Revises: e406db00d0fa
Create Date: 2026-02-07 20:39:02.804762

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a881e873d6f2'
down_revision = 'e406db00d0fa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lot_id', sa.Integer(), nullable=True),
        sa.Column('message_guid', sa.UUID(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('extracted_data', sa.JSON(), nullable=True),
        sa.Column('downloaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lot_id'], ['lots.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_lot_id'), 'documents', ['lot_id'], unique=False)
    op.create_index(op.f('ix_documents_message_guid'), 'documents', ['message_guid'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_documents_message_guid'), table_name='documents')
    op.drop_index(op.f('ix_documents_lot_id'), table_name='documents')
    op.drop_table('documents')