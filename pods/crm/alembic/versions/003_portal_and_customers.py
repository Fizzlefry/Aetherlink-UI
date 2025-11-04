"""Portal and customers

Revision ID: 003_portal_and_customers
Revises: 002_sprint_0_foundation
Create Date: 2025-11-02 15:35:00.000000

"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    # Customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("full_name", sa.String(200)),
        sa.Column("phone", sa.String(50)),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
    )
    op.create_index("ix_customers_org_id", "customers", ["org_id"])

    # Portal tokens for secure access
    op.create_table(
        "customer_portal_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("org_id", sa.Integer, nullable=False),
        sa.Column("customer_id", sa.Integer, nullable=False),
        sa.Column("proposal_id", sa.Integer, nullable=True),
        sa.Column("token", sa.String(512), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("used_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_cpt_org_id", "customer_portal_tokens", ["org_id"])

    # Activity log for portal events
    op.create_table(
        "portal_activity_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False),
        sa.Column("proposal_id", sa.Integer, nullable=True),
        sa.Column("event", sa.String(50), nullable=False),  # view|approve|download|email_sent
        sa.Column("meta", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("portal_activity_log")
    op.drop_index("ix_cpt_org_id", table_name="customer_portal_tokens")
    op.drop_table("customer_portal_tokens")
    op.drop_index("ix_customers_org_id", table_name="customers")
    op.drop_table("customers")
