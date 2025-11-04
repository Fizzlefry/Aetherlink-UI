"""add lead_notes table

Revision ID: 3e71232cb975
Revises: b21f487d9ec2
Create Date: 2025-11-03 15:23:30.132293

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e71232cb975'
down_revision: Union[str, Sequence[str], None] = 'b21f487d9ec2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create lead_notes table
    op.create_table(
        'lead_notes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(160), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('author', sa.String(160), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE', name='fk_lead_notes_lead'),
    )
    
    # Create index for efficient tenant+lead queries
    op.create_index(
        'ix_lead_notes_lead_tenant',
        'lead_notes',
        ['tenant_id', 'lead_id', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_lead_notes_lead_tenant', table_name='lead_notes')
    op.drop_table('lead_notes')
