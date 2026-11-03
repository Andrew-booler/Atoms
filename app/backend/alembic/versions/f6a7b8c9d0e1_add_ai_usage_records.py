"""add ai usage records

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-04 05:10:00.000000

每次 AI 调用落一行用量；token 字段可空，模拟输出只记 null 不伪造数字。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_usage_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('build_id', sa.String(length=64), nullable=True),
        sa.Column('stage', sa.String(length=32), nullable=True),
        sa.Column('provider', sa.String(length=64), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('reasoning_tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_usage_records_user_id', 'ai_usage_records', ['user_id'], unique=False)
    op.create_index('ix_ai_usage_records_build_id', 'ai_usage_records', ['build_id'], unique=False)
    op.create_index('ix_ai_usage_records_created_at', 'ai_usage_records', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ai_usage_records_created_at', table_name='ai_usage_records')
    op.drop_index('ix_ai_usage_records_build_id', table_name='ai_usage_records')
    op.drop_index('ix_ai_usage_records_user_id', table_name='ai_usage_records')
    op.drop_table('ai_usage_records')
