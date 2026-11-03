"""后端-单元-01 至 04：services/studio_output.py 的输出边界。

纯函数与实例方法，不连接数据库、不发网络请求。
"""
from services import studio_output

HYDRATION_REQ = "一个记录每日饮水量的追踪器，带进度环"


def test_get_provider_default_and_injection():
    original = studio_output._provider
    try:
        default = studio_output.get_provider()
        assert isinstance(default, studio_output.MockOutputProvider)

        class FakeProvider:
            pass

        studio_output._provider = FakeProvider()
        assert studio_output.get_provider() is studio_output._provider
        assert not isinstance(studio_output.get_provider(), studio_output.MockOutputProvider)
    finally:
        studio_output._provider = original


async def test_mock_provider_example_plan_outline():
    provider = studio_output.MockOutputProvider()

    plan = await provider.plan(HYDRATION_REQ)
    assert plan["summary"] == "做一个带进度环的每日饮水追踪器"
    assert {step["title"] for step in plan["steps"]} == {"搭建进度环", "杯量快捷记录", "今日记录"}

    outline = await provider.outline(HYDRATION_REQ, plan)
    assert outline["title"] == "每日饮水追踪器"
    assert [section["name"] for section in outline["sections"]] == ["进度概览", "快捷记录", "今日记录"]


async def test_mock_provider_generic_plan_outline():
    provider = studio_output.MockOutputProvider()

    plan = await provider.plan("做个完全无关的东西")
    assert plan["summary"] == "演示通用可交互原型"

    outline = await provider.outline("做个完全无关的东西", plan)
    assert outline["title"] == "原型预览"


async def test_mock_provider_deepcopy_isolation():
    provider = studio_output.MockOutputProvider()

    plan1 = await provider.plan(HYDRATION_REQ)
    plan1["summary"] = "MUTATED"
    plan1["steps"][0]["title"] = "MUTATED"

    plan1_again = await provider.plan(HYDRATION_REQ)
    assert plan1_again["summary"] == "做一个带进度环的每日饮水追踪器"
    assert plan1_again["steps"][0]["title"] == "搭建进度环"
    assert plan1_again is not plan1


async def test_artifact_returns_example_html():
    provider = studio_output.MockOutputProvider()
    html = await provider.artifact(HYDRATION_REQ, {}, {})
    assert "<!DOCTYPE html>" in html
    assert "<body" in html
    assert "</html>" in html
    assert "每日饮水追踪器" in html


def test_resolve_model_and_available_models():
    models = studio_output.available_models()
    assert [m["key"] for m in models] == ["balanced", "fast", "quality"]
    for m in models:
        assert m["model"] == "mock-fixed-v1"
    for profile in (None, "balanced", "fast", "quality", "unknown"):
        assert studio_output.resolve_model(profile) == "mock-fixed-v1"


def _patch_ai(monkeypatch, calls):
    async def fake_plan(requirement, **kwargs):
        calls.append(("plan", requirement, kwargs))
        return {"summary": "计划"}

    async def fake_outline(requirement, plan, **kwargs):
        calls.append(("outline", requirement, kwargs))
        return {"title": "结构"}

    async def fake_artifact(requirement, plan, outline, **kwargs):
        calls.append(("artifact", requirement, kwargs))
        return "<html></html>"

    monkeypatch.setattr(studio_output.studio_ai, "generate_plan", fake_plan)
    monkeypatch.setattr(studio_output.studio_ai, "generate_outline", fake_outline)
    monkeypatch.setattr(studio_output.studio_ai, "generate_artifact", fake_artifact)


async def test_real_output_provider_short_circuits_example(monkeypatch):
    calls = []
    _patch_ai(monkeypatch, calls)
    provider = studio_output.RealOutputProvider()

    plan = await provider.plan(HYDRATION_REQ)
    assert plan["summary"] == "做一个带进度环的每日饮水追踪器"
    outline = await provider.outline(HYDRATION_REQ, plan)
    assert outline["title"] == "每日饮水追踪器"
    html = await provider.artifact(HYDRATION_REQ, plan, outline)
    assert "每日饮水追踪器" in html
    assert "进度环" in html
    assert calls == []


async def test_real_output_provider_delegates(monkeypatch):
    calls = []
    _patch_ai(monkeypatch, calls)
    provider = studio_output.RealOutputProvider()

    assert await provider.plan("做个完全无关的东西", project_name="x", profile=None) == {"summary": "计划"}
    assert await provider.outline("做个完全无关的东西", {}, profile=None) == {"title": "结构"}
    assert await provider.artifact("做个完全无关的东西", {}, {}, profile=None) == "<html></html>"
    assert [c[0] for c in calls] == ["plan", "outline", "artifact"]