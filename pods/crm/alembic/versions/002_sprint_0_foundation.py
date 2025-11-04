"""Sprint 0: Multi-tenant foundation + opportunities + jobs + pgvector

Revision ID: 002_sprint_0_foundation
Revises: 001_initial_schema
Create Date: 2025-11-02 14:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create orgs table
    op.create_table(
        'orgs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('subdomain', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orgs_id'), 'orgs', ['id'], unique=False)
    op.create_index(op.f('ix_orgs_subdomain'), 'orgs', ['subdomain'], unique=True)
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['orgs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_org_id'), 'users', ['org_id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['orgs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_roles_id'), 'roles', ['id'], unique=False)
    op.create_index(op.f('ix_roles_org_id'), 'roles', ['org_id'], unique=False)
    
    # Create user_roles table
    op.create_table(
        'user_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_roles_id'), 'user_roles', ['id'], unique=False)
    op.create_index(op.f('ix_user_roles_user_id'), 'user_roles', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_roles_role_id'), 'user_roles', ['role_id'], unique=False)
    
    # Create permissions table
    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('resource', sa.String(length=100), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_permissions_id'), 'permissions', ['id'], unique=False)
    op.create_index(op.f('ix_permissions_role_id'), 'permissions', ['role_id'], unique=False)
    
    # Add org_id to existing leads table
    op.add_column('leads', sa.Column('org_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_leads_org_id', 'leads', 'orgs', ['org_id'], ['id'])
    op.create_index(op.f('ix_leads_org_id'), 'leads', ['org_id'], unique=False)
    
    # Add new fields to leads for AI scoring
    op.add_column('leads', sa.Column('score', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('leads', sa.Column('heat_level', sa.String(length=20), nullable=True, server_default='cold'))
    op.add_column('leads', sa.Column('converted_at', sa.DateTime(), nullable=True))
    
    # Add org_id to existing projects table
    op.add_column('projects', sa.Column('org_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_projects_org_id', 'projects', 'orgs', ['org_id'], ['id'])
    op.create_index(op.f('ix_projects_org_id'), 'projects', ['org_id'], unique=False)
    
    # Add org_id to existing contacts table
    op.add_column('contacts', sa.Column('org_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_contacts_org_id', 'contacts', 'orgs', ['org_id'], ['id'])
    op.create_index(op.f('ix_contacts_org_id'), 'contacts', ['org_id'], unique=False)
    
    # Create opportunities table
    op.create_table(
        'opportunities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('stage', sa.String(length=50), nullable=True, server_default='qualification'),
        sa.Column('probability', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('value', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['orgs.id'], ),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_opportunities_id'), 'opportunities', ['id'], unique=False)
    op.create_index(op.f('ix_opportunities_org_id'), 'opportunities', ['org_id'], unique=False)
    op.create_index(op.f('ix_opportunities_lead_id'), 'opportunities', ['lead_id'], unique=False)
    
    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('site_address', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='scheduled'),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('crew_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('notes_embedding', Vector(1536), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['orgs.id'], ),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_id'), 'jobs', ['id'], unique=False)
    op.create_index(op.f('ix_jobs_org_id'), 'jobs', ['org_id'], unique=False)
    op.create_index(op.f('ix_jobs_opportunity_id'), 'jobs', ['opportunity_id'], unique=False)
    
    # Create attachments table
    op.create_table(
        'attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('key', sa.String(length=500), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['orgs.id'], ),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attachments_id'), 'attachments', ['id'], unique=False)
    op.create_index(op.f('ix_attachments_org_id'), 'attachments', ['org_id'], unique=False)
    op.create_index(op.f('ix_attachments_job_id'), 'attachments', ['job_id'], unique=False)


def downgrade() -> None:
    # Drop new tables
    op.drop_table('attachments')
    op.drop_table('jobs')
    op.drop_table('opportunities')
    op.drop_table('permissions')
    op.drop_table('user_roles')
    op.drop_table('roles')
    op.drop_table('users')
    op.drop_table('orgs')
    
    # Remove org_id from existing tables
    op.drop_column('contacts', 'org_id')
    op.drop_column('projects', 'org_id')
    op.drop_column('leads', 'converted_at')
    op.drop_column('leads', 'heat_level')
    op.drop_column('leads', 'score')
    op.drop_column('leads', 'org_id')
    
    # Drop pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
