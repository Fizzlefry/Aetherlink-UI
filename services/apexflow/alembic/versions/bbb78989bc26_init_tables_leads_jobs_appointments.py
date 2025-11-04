"""init tables: leads, jobs, appointments

Revision ID: bbb78989bc26
Revises: 
Create Date: 2025-11-03 08:34:24.699159

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbb78989bc26'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create leads table
    op.create_table(
        'leads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('email', sa.String(length=160), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_leads_tenant_id', 'leads', ['tenant_id'], unique=False)
    op.create_index('ix_leads_tenant_email_unique', 'leads', ['tenant_id', 'email'], unique=True, 
                    postgresql_where=sa.text('email IS NOT NULL'))
    op.create_index('ix_leads_tenant_phone', 'leads', ['tenant_id', 'phone'], unique=False)
    op.create_index('ix_leads_tenant_created', 'leads', ['tenant_id', 'created_at'], unique=False)

    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_jobs_tenant_id', 'jobs', ['tenant_id'], unique=False)
    op.create_index('ix_jobs_tenant_status', 'jobs', ['tenant_id', 'status'], unique=False)
    op.create_index('ix_jobs_tenant_lead', 'jobs', ['tenant_id', 'lead_id'], unique=False)

    # Create appointments table
    op.create_table(
        'appointments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column('type', sa.String(length=64), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_appointments_tenant_id', 'appointments', ['tenant_id'], unique=False)
    op.create_index('ix_appt_tenant_scheduled', 'appointments', ['tenant_id', 'scheduled_at'], unique=False)
    op.create_index('ix_appt_tenant_lead', 'appointments', ['tenant_id', 'lead_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_appt_tenant_lead', table_name='appointments')
    op.drop_index('ix_appt_tenant_scheduled', table_name='appointments')
    op.drop_index('ix_appointments_tenant_id', table_name='appointments')
    op.drop_table('appointments')
    
    op.drop_index('ix_jobs_tenant_lead', table_name='jobs')
    op.drop_index('ix_jobs_tenant_status', table_name='jobs')
    op.drop_index('ix_jobs_tenant_id', table_name='jobs')
    op.drop_table('jobs')
    
    op.drop_index('ix_leads_tenant_created', table_name='leads')
    op.drop_index('ix_leads_tenant_phone', table_name='leads')
    op.drop_index('ix_leads_tenant_email_unique', table_name='leads')
    op.drop_index('ix_leads_tenant_id', table_name='leads')
    op.drop_table('leads')
