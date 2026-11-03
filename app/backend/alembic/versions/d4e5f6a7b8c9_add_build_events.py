"""add build events for build terminal

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-11-04 03:40:00.000000

构建终端事件表：按 (user_id, project_id, build_id) 归属，seq 为一次构建内的递增序号，
刷新页面后可回放最近一次构建；不修改既有 message/version 表。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'build_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('build_id', sa.String(length=64), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=32), nullable=False),
        sa.Column('stage', sa.String(length=32), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_build_events_user_id', 'build_events', ['user_id'])
    op.create_index('ix_build_events_project_id', 'build_events', ['project_id'])
    op.create_index('ix_build_events_build_id', 'build_events', ['build_id'])


def downgrade() -> None:
    op.drop_index('ix_build_events_build_id', table_name='build_events')
    op.drop_index('ix_build_events_project_id', table_name='build_events')
    op.drop_index('ix_build_events_user_id', table_name='build_events')
    op.drop_table('build_events')
