"""add lead lifecycle fields: status, assigned_to, tags, is_archived

Revision ID: 349c4cb76c26
Revises: 6abda15b043b
Create Date: 2025-11-03 14:41:06.210384

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "349c4cb76c26"
down_revision: str | Sequence[str] | None = "6abda15b043b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
