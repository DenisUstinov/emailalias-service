"""Remove alias status provisioned and forwarded

Revision ID: 7391cba70b93
Revises: 17c7bcc991f6
Create Date: 2026-07-08 00:32:27.669821

"""
from typing import Union
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '7391cba70b93'
down_revision: str | Sequence[str] | None = '17c7bcc991f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint('aliasstatus', 'aliases', type_='check')
    with op.batch_alter_table('aliases', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=sa.String(),
               type_=sa.Enum('PENDING', 'ACTIVE', 'FAILED', 'DELETING', name='aliasstatus', native_enum=False, create_constraint=True),
               existing_nullable=False,
               existing_server_default=sa.text("'pending'::character varying"))


def downgrade() -> None:
    op.drop_constraint('aliasstatus', 'aliases', type_='check')
    with op.batch_alter_table('aliases', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=sa.String(),
               type_=sa.Enum('PENDING', 'PROVISIONED', 'FORWARDED', 'ACTIVE', 'FAILED', 'DELETING', name='aliasstatus', native_enum=False, create_constraint=True),
               existing_nullable=False,
               existing_server_default=sa.text("'pending'::character varying"))
