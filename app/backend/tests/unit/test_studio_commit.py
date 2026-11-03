"""后端-单元-08：routers/studio.py::_commit 提交失败映射。"""
import pytest

from core import error_codes
from core.exceptions import InternalError
from routers import studio


class FailingSession:
    def __init__(self):
        self.rollbacks = 0

    async def commit(self):
        raise RuntimeError("boom")

    async def rollback(self):
        self.rollbacks += 1


async def test_commit_failure_maps_to_500():
    session = FailingSession()
    with pytest.raises(InternalError) as exc_info:
        await studio._commit(session)
    assert exc_info.value.http_status == 500
    assert exc_info.value.code == error_codes.STUDIO_DB_COMMIT_FAILED
    assert exc_info.value.message == "保存数据失败，请稍后重试。"
    assert session.rollbacks == 1