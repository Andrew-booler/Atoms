"""后端-单元-08：routers/studio.py::_commit 提交失败映射。"""
import pytest
from fastapi import HTTPException

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
    with pytest.raises(HTTPException) as exc_info:
        await studio._commit(session)
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "保存失败，未提交本次变更，请重试"
    assert session.rollbacks == 1