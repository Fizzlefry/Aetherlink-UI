"""QBO links for customers and proposals

Revision ID: 005_qbo_links
Revises: 004_qbo_tokens
Create Date: 2025-11-02
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005_qbo_links'
down_revision = '004_qbo_tokens'
branch_labels = None
depends_on = None


def upgrade():
    """Add QuickBooks tracking columns to customers and proposals."""
    
    # Add QBO columns to customers table
    op.add_column('customers', sa.Column('qbo_customer_id', sa.String(64), nullable=True))
    op.add_column('customers', sa.Column('qbo_last_sync_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_customers_qbo_customer_id', 'customers', ['qbo_customer_id'])
    
    # Add QBO columns to leads table (proposals stored here in Sprint 1)
    # Note: If you have a separate proposals table, adjust accordingly
    op.add_column('leads', sa.Column('qbo_invoice_id', sa.String(64), nullable=True))
    op.add_column('leads', sa.Column('qbo_invoice_number', sa.String(64), nullable=True))
    op.add_column('leads', sa.Column('qbo_status', sa.String(24), nullable=True))
    op.add_column('leads', sa.Column('qbo_balance_cents', sa.Integer(), nullable=True))
    op.add_column('leads', sa.Column('qbo_paid_cents', sa.Integer(), nullable=True))
    op.add_column('leads', sa.Column('qbo_last_sync_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_leads_qbo_invoice_id', 'leads', ['qbo_invoice_id'])


def downgrade():
    """Remove QuickBooks tracking columns."""
    
    # Remove indexes
    op.drop_index('ix_leads_qbo_invoice_id', 'leads')
    op.drop_index('ix_customers_qbo_customer_id', 'customers')
    
    # Remove columns from leads
    op.drop_column('leads', 'qbo_last_sync_at')
    op.drop_column('leads', 'qbo_paid_cents')
    op.drop_column('leads', 'qbo_balance_cents')
    op.drop_column('leads', 'qbo_status')
    op.drop_column('leads', 'qbo_invoice_number')
    op.drop_column('leads', 'qbo_invoice_id')
    
    # Remove columns from customers
    op.drop_column('customers', 'qbo_last_sync_at')
    op.drop_column('customers', 'qbo_customer_id')
