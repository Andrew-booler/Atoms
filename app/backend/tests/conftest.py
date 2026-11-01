"""测试套件根配置。

测试宿主 testing/studio_app.py 在模块导入时读取 DATABASE_URL（见其第 16 行）。
单元测试不连接数据库，仅需该变量存在即可导入；接口集成测试在 integration/conftest.py
中覆盖为真实 PostgreSQL 连接并探测可用性。默认值指向本机常见开发库，可用环境变量覆盖。
"""
import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
)