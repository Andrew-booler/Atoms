"""add executions table

Revision ID: a1f2e3d4c5b6
Revises: 271a19c82eca
Create Date: 2026-11-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f2e3d4c5b6'
down_revision: Union[str, Sequence[str], None] = '271a19c82eca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('version_id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.String(length=128), nullable=True),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='running'),
        sa.Column('preview_url', sa.String(length=255), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_executions_id'), 'executions', ['id'], unique=False)
    op.create_index(op.f('ix_executions_version_id'), 'executions', ['version_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_executions_version_id'), table_name='executions')
    op.drop_index(op.f('ix_executions_id'), table_name='executions')
    op.drop_table('executions')
