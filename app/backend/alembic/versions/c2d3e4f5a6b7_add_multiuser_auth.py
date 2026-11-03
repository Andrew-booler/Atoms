"""add multi-user auth and execution ownership

Revision ID: c2d3e4f5a6b7
Revises: b7c8d9e0f1a2
Create Date: 2026-11-04 00:00:00.000000

- users 增加 password_hash / is_legacy，并为 email 建立唯一索引
- 幂等创建 legacy 用户，把存量共享数据回填到该用户
- executions 增加 user_id，回填后设为非空
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_USER_ID = 'legacy'
LEGACY_USER_EMAIL = 'legacy@atoms.local'
SHARED_CONTEXT = 'studio-shared'


def upgrade() -> None:
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column(
        'users',
        sa.Column('is_legacy', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 幂等创建历史共享数据归属账户：没有密码，不能被登录。
    op.execute(
        f"""
        INSERT INTO users (id, email, name, role, password_hash, is_legacy)
        VALUES ('{LEGACY_USER_ID}', '{LEGACY_USER_EMAIL}', '历史共享数据', 'user', NULL, true)
        ON CONFLICT DO NOTHING
        """
    )

    # 存量共享数据归到 legacy 用户，不删除、不置空。
    for table in ('projects', 'studio_messages', 'studio_versions'):
        op.execute(
            f"UPDATE {table} SET user_id = '{LEGACY_USER_ID}' "
            f"WHERE user_id = '{SHARED_CONTEXT}'"
        )

    op.add_column('executions', sa.Column('user_id', sa.String(length=255), nullable=True))
    op.execute(f"UPDATE executions SET user_id = '{LEGACY_USER_ID}' WHERE user_id IS NULL")
    op.alter_column('executions', 'user_id', existing_type=sa.String(length=255), nullable=False)
    op.create_index(op.f('ix_executions_user_id'), 'executions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_executions_user_id'), table_name='executions')
    op.drop_column('executions', 'user_id')

    # 仅移除本迁移创建的历史账户，避免误删真实用户。
    op.execute(f"DELETE FROM users WHERE id = '{LEGACY_USER_ID}' AND is_legacy = true")

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_column('users', 'is_legacy')
    op.drop_column('users', 'password_hash')
