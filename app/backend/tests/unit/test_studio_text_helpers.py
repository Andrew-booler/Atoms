"""后端-单元-05/06/07：routers/studio.py 的纯文本整理与容错解析。"""
from routers import studio
from schemas.studio import PlanPayload


def test_plan_to_text():
    payload = PlanPayload(
        summary="演示计划一",
        steps=[
            {"title": "显示演示", "detail": "使用预置页面"},
            {"title": "显示备注", "detail": ""},
        ],
        files=[{"path": "index.html"}, {"path": "app.js"}],
    )
    result = studio._plan_to_text(payload)
    assert result == (
        "演示计划一\n\n1. 显示演示 — 使用预置页面\n2. 显示备注\n\n产出文件：index.html、app.js"
    )
    # 第二个步骤不出现孤立破折号，整体首尾空白被去除
    assert "显示备注 —" not in result
    assert not result.startswith("\n") and not result.endswith("\n")


def test_plan_request_text_with_and_without_steps():
    full = {"summary": "摘要", "steps": [{"title": "T1", "detail": "D1"}, {"title": "T2", "detail": ""}]}
    assert studio._plan_request_text(full) == "摘要\n\n1. T1 — D1\n2. T2 — "

    empty = {"summary": "摘要", "steps": []}
    result = studio._plan_request_text(empty)
    assert result == "摘要\n"
    assert result.endswith("\n")  # 末尾换行未被裁剪


def test_parse_meta_tolerates_invalid():
    assert studio._parse_meta(None) == {}
    assert studio._parse_meta("") == {}
    assert studio._parse_meta("不是JSON") == {}
    assert studio._parse_meta("[1, 2]") == {}
    assert studio._parse_meta('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}