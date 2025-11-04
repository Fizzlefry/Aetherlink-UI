"""add lead lifecycle fields

Revision ID: b21f487d9ec2
Revises: 349c4cb76c26
Create Date: 2025-11-03 14:41:16.900119

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b21f487d9ec2'
down_revision: Union[str, Sequence[str], None] = '349c4cb76c26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add CRM lifecycle fields to leads."""
    # Add status column with constraint
    op.add_column('leads', sa.Column('status', sa.String(32), nullable=False, server_default='new'))
    op.create_check_constraint(
        'ck_leads_status',
        'leads',
        "status IN ('new', 'contacted', 'qualified', 'proposal', 'won', 'lost')"
    )
    
    # Add assigned_to column (nullable - unassigned leads are valid)
    op.add_column('leads', sa.Column('assigned_to', sa.String(160), nullable=True))
    
    # Add tags as JSONB array
    op.add_column('leads', sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'))
    
    # Add soft delete flag
    op.add_column('leads', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'))
    
    # Create indexes for filtering
    op.create_index('ix_leads_status', 'leads', ['status'])
    op.create_index('ix_leads_assigned_to', 'leads', ['assigned_to'])
    op.create_index('ix_leads_is_archived', 'leads', ['is_archived'])
    op.create_index('ix_leads_tenant_status', 'leads', ['tenant_id', 'status'])


def downgrade() -> None:
    """Downgrade schema - remove CRM lifecycle fields."""
    op.drop_index('ix_leads_tenant_status', table_name='leads')
    op.drop_index('ix_leads_is_archived', table_name='leads')
    op.drop_index('ix_leads_assigned_to', table_name='leads')
    op.drop_index('ix_leads_status', table_name='leads')
    
    op.drop_column('leads', 'is_archived')
    op.drop_column('leads', 'tags')
    op.drop_column('leads', 'assigned_to')
    
    op.drop_constraint('ck_leads_status', 'leads')
    op.drop_column('leads', 'status')
