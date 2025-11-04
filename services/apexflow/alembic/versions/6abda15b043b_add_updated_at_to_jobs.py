"""add updated_at to jobs

Revision ID: 6abda15b043b
Revises: bbb78989bc26
Create Date: 2025-11-03 09:49:47.288772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6abda15b043b'
down_revision: Union[str, Sequence[str], None] = 'bbb78989bc26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'updated_at')
