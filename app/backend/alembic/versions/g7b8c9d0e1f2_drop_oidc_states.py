"""移除未使用的 OIDCState 表（OIDC 登录路径已删除）。

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-04 06:05:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'g7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('oidc_states')


def downgrade() -> None:
    import sqlalchemy as sa

    op.create_table(
        'oidc_states',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('state', sa.String(length=255), nullable=False),
        sa.Column('nonce', sa.String(length=255), nullable=False),
        sa.Column('code_verifier', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('state'),
    )
    op.create_index('ix_oidc_states_id', 'oidc_states', ['id'], unique=False)
    op.create_index('ix_oidc_states_state', 'oidc_states', ['state'], unique=True)
