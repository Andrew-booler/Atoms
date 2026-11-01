"""后端-单元-01 至 04：services/studio_output.py 的输出边界。

纯函数与实例方法，不连接数据库、不发网络请求。
"""
from services import studio_output


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


async def test_mock_provider_plan_outline_deepcopy():
    provider = studio_output.MockOutputProvider()

    plan1 = await provider.plan("记录饮水")
    plan2 = await provider.plan("增加备注")
    assert plan1["summary"] == "演示计划一"
    assert plan2["summary"] == "演示计划二"

    plan1["summary"] = "MUTATED"
    plan1["steps"][0]["title"] = "MUTATED"
    plan1_again = await provider.plan("记录饮水")
    assert plan1_again["summary"] == "演示计划一"
    assert plan1_again["steps"][0]["title"] == "显示演示"
    assert plan1_again is not plan1

    outline1 = await provider.outline("记录饮水", plan1)
    outline2 = await provider.outline("增加备注", plan2)
    assert outline1["title"] == "演示页面一"
    assert outline2["title"] == "演示页面二"


def test_fixed_html_versions():
    v1 = studio_output.fixed_html()
    v2 = studio_output.fixed_html(second=True)
    assert "模拟第一版" in v1
    assert "模拟第二版" in v2
    for html in (v1, v2):
        assert "<!DOCTYPE html>" in html
        assert "<body" in html
        assert "</html>" in html
        assert "演示计数" in html


async def test_artifact_returns_fixed_html():
    provider = studio_output.MockOutputProvider()
    assert await provider.artifact("记录饮水", {}, {}) == studio_output.fixed_html()
    assert await provider.artifact("增加备注", {}, {}) == studio_output.fixed_html(second=True)


def test_resolve_model_and_available_models():
    models = studio_output.available_models()
    assert [m["key"] for m in models] == ["balanced", "fast", "quality"]
    for m in models:
        assert m["model"] == "mock-fixed-v1"
    for profile in (None, "balanced", "fast", "quality", "unknown"):
        assert studio_output.resolve_model(profile) == "mock-fixed-v1"


async def test_real_output_provider_delegates():
    class RecordingAdapter:
        def __init__(self):
            self.calls = []

        async def plan(self, requirement, **kwargs):
            self.calls.append(("plan", requirement))
            return {"summary": "计划"}

        async def outline(self, requirement, plan, **kwargs):
            self.calls.append(("outline", requirement))
            return {"title": "结构"}

        async def artifact(self, requirement, plan, outline, **kwargs):
            self.calls.append(("artifact", requirement))
            return "<html></html>"

    adapter = RecordingAdapter()
    provider = studio_output.RealOutputProvider(adapter)

    assert await provider.plan("需求", project_name="x", profile=None) == {"summary": "计划"}
    assert await provider.outline("需求", {}, profile=None) == {"title": "结构"}
    assert await provider.artifact("需求", {}, {}, profile=None) == "<html></html>"
    assert [c[0] for c in adapter.calls] == ["plan", "outline", "artifact"]