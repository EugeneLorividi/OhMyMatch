"""Drop recovery code

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('users', 'recovery_code_hash')


def downgrade() -> None:
    """Downgrade schema."""
    # Old codes are gone for good; restored rows get an empty hash that matches nothing.
    op.add_column('users', sa.Column('recovery_code_hash', sa.String(length=255), server_default='', nullable=False))
    op.alter_column('users', 'recovery_code_hash', server_default=None)
