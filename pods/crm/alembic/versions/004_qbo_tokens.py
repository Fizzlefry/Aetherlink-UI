"""QBO OAuth tokens storage

Revision ID: 004_qbo_tokens
Revises: 003
Create Date: 2025-11-02
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "004_qbo_tokens"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    """Create qbo_tokens table for secure OAuth token storage."""
    op.create_table(
        "qbo_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, nullable=False),
        sa.Column("realm_id", sa.String(32), nullable=True),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("env", sa.String(16), nullable=False, server_default="sandbox"),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )

    # Create indexes
    op.create_index("ix_qbo_tokens_org_id", "qbo_tokens", ["org_id"])
    op.create_index("ix_qbo_tokens_realm_id", "qbo_tokens", ["realm_id"])

    # Create unique constraint
    op.create_unique_constraint("uq_qbo_tokens_org", "qbo_tokens", ["org_id"])


def downgrade():
    """Drop qbo_tokens table."""
    op.drop_table("qbo_tokens")
