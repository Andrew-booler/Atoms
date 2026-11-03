"""后端-单元：services/studio_ai.py 各阶段输出预算。

用录制式替身替换 AIHubService，不发网络请求，只校验传给模型请求的 max_completion_tokens（含思考预算换算）。
"""

import json

from schemas.aihub import GenTxtResponse
from services import studio_ai

PLAN_JSON = json.dumps(
    {"summary": "计划", "steps": [{"title": "步骤"}], "files": [], "stack": []},
    ensure_ascii=False,
)
OUTLINE_JSON = json.dumps(
    {
        "title": "原型",
        "sections": [{"name": "区块", "blocks": ["内容项"]}],
        "interactions": [],
        "seed_data": [],
    },
    ensure_ascii=False,
)
HTML = "<!DOCTYPE html><html><head></head><body><h1>原型</h1></body></html>"


class _RecordingService:
    """记录每次请求的替身，返回固定内容。"""

    def __init__(self, content: str):
        self.content = content
        self.requests = []

    async def gentxt(self, request):
        self.requests.append(request)
        return GenTxtResponse(content=self.content, model=request.model)


def _patch(monkeypatch, content: str) -> _RecordingService:
    service = _RecordingService(content)
    monkeypatch.setattr(studio_ai, "AIHubService", lambda: service)
    return service


async def test_stage_max_tokens_defaults_thinking_disabled(monkeypatch):
    """默认关闭思考：可见预算 + 1024 余量（plan 2624 / outline 3224 / artifact 7168）。"""
    monkeypatch.delenv("APP_AI_ENABLE_THINKING", raising=False)
    plan_service = _patch(monkeypatch, PLAN_JSON)
    await studio_ai.generate_plan("做一个待办清单", project_name="待办")
    assert plan_service.requests[0].max_completion_tokens == 1600 + 1024

    outline_service = _patch(monkeypatch, OUTLINE_JSON)
    await studio_ai.generate_outline("做一个待办清单", {"summary": "计划", "steps": []})
    assert outline_service.requests[0].max_completion_tokens == 2200 + 1024

    artifact_service = _patch(monkeypatch, HTML)
    await studio_ai.generate_artifact("做一个待办清单", {"summary": "计划"}, {"title": "原型"})
    assert artifact_service.requests[0].max_completion_tokens == 6144 + 1024


async def test_stage_request_tokens_thinking_enabled(monkeypatch):
    """开启思考：可见预算 + thinking_budget(2048) + 1024 余量，artifact 总量 9216。"""
    monkeypatch.setenv("APP_AI_ENABLE_THINKING", "true")
    monkeypatch.delenv("APP_STUDIO_THINKING_BUDGET", raising=False)

    plan_service = _patch(monkeypatch, PLAN_JSON)
    await studio_ai.generate_plan("做一个待办清单", project_name="待办")
    assert plan_service.requests[0].max_completion_tokens == 1600 + 2048 + 1024

    outline_service = _patch(monkeypatch, OUTLINE_JSON)
    await studio_ai.generate_outline("做一个待办清单", {"summary": "计划", "steps": []})
    assert outline_service.requests[0].max_completion_tokens == 2200 + 2048 + 1024

    artifact_service = _patch(monkeypatch, HTML)
    await studio_ai.generate_artifact("做一个待办清单", {"summary": "计划"}, {"title": "原型"})
    assert artifact_service.requests[0].max_completion_tokens == 6144 + 2048 + 1024 == 9216


async def test_stage_max_tokens_env_override(monkeypatch):
    """各阶段可见预算可由独立环境变量覆盖，互不影响。"""
    monkeypatch.setenv("APP_STUDIO_PLAN_MAX_TOKENS", "1200")
    monkeypatch.setenv("APP_STUDIO_OUTLINE_MAX_TOKENS", "1800")
    monkeypatch.setenv("APP_STUDIO_ARTIFACT_MAX_TOKENS", "8192")
    monkeypatch.delenv("APP_AI_ENABLE_THINKING", raising=False)

    plan_service = _patch(monkeypatch, PLAN_JSON)
    await studio_ai.generate_plan("做一个待办清单", project_name="待办")
    assert plan_service.requests[0].max_completion_tokens == 1200 + 1024

    outline_service = _patch(monkeypatch, OUTLINE_JSON)
    await studio_ai.generate_outline("做一个待办清单", {"summary": "计划", "steps": []})
    assert outline_service.requests[0].max_completion_tokens == 1800 + 1024

    artifact_service = _patch(monkeypatch, HTML)
    await studio_ai.generate_artifact("做一个待办清单", {"summary": "计划"}, {"title": "原型"})
    assert artifact_service.requests[0].max_completion_tokens == 8192 + 1024


async def test_stage_max_tokens_env_invalid_falls_back(monkeypatch):
    """环境变量非法时回落默认值，不影响生成。"""
    monkeypatch.setenv("APP_STUDIO_ARTIFACT_MAX_TOKENS", "not-a-number")
    monkeypatch.delenv("APP_AI_ENABLE_THINKING", raising=False)

    artifact_service = _patch(monkeypatch, HTML)
    await studio_ai.generate_artifact("做一个待办清单", {"summary": "计划"}, {"title": "原型"})
    assert artifact_service.requests[0].max_completion_tokens == 6144 + 1024
