"""Add alias status provisioned

Revision ID: c60a3cec4269
Revises: 25349345103a
Create Date: 2026-07-02 03:17:18.723565

"""
from typing import Union
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c60a3cec4269'
down_revision: str | Sequence[str] | None = '25349345103a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('aliasstatus', 'aliases', type_='check')
    with op.batch_alter_table('aliases', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=sa.VARCHAR(length=8),
               type_=sa.Enum('PENDING', 'PROVISIONED', 'ACTIVE', 'FAILED', 'DELETING', name='aliasstatus', native_enum=False, create_constraint=True),
               existing_nullable=False,
               existing_server_default=sa.text("'pending'::character varying"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('aliasstatus', 'aliases', type_='check')
    with op.batch_alter_table('aliases', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=sa.Enum('PENDING', 'PROVISIONED', 'ACTIVE', 'FAILED', 'DELETING', name='aliasstatus', native_enum=False, create_constraint=True),
               type_=sa.VARCHAR(length=8),
               existing_nullable=False,
               existing_server_default=sa.text("'pending'::character varying"))
