"""Add alias status forwarded

Revision ID: 17c7bcc991f6
Revises: c60a3cec4269
Create Date: 2026-07-06 00:56:53.648281

"""
from typing import Union
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '17c7bcc991f6'
down_revision: str | Sequence[str] | None = 'c60a3cec4269'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint('aliasstatus', 'aliases', type_='check')
    with op.batch_alter_table('aliases', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=sa.String(),
               type_=sa.Enum('PENDING', 'PROVISIONED', 'FORWARDED', 'ACTIVE', 'FAILED', 'DELETING', name='aliasstatus', native_enum=False, create_constraint=True),
               existing_nullable=False,
               existing_server_default=sa.text("'pending'::character varying"))


def downgrade() -> None:
    op.drop_constraint('aliasstatus', 'aliases', type_='check')
    with op.batch_alter_table('aliases', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=sa.String(),
               type_=sa.Enum('PENDING', 'PROVISIONED', 'ACTIVE', 'FAILED', 'DELETING', name='aliasstatus', native_enum=False, create_constraint=True),
               existing_nullable=False,
               existing_server_default=sa.text("'pending'::character varying"))
