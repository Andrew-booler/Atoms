"""后端-单元-09/10/11：services/studio_validation.py 结构校验纯函数。

纯函数抛出 ValueError；路由层将其映射为 HTTP 502（状态码由接口集成与故障注入覆盖）。
"""
import pytest

from services.studio_validation import (
    validate_artifact_html,
    validate_outline_payload,
    validate_plan_payload,
)


def test_validate_plan_payload():
    with pytest.raises(ValueError, match="模拟计划结构无效"):
        validate_plan_payload({"summary": "x"})  # 缺 steps
    with pytest.raises(ValueError, match="模拟计划结构无效"):
        validate_plan_payload({"summary": "x", "steps": [{"detail": "d"}]})  # 步骤缺 title
    payload = validate_plan_payload({"summary": "x", "steps": [{"title": "t"}]})
    assert payload.summary == "x"
    assert payload.steps == [{"title": "t"}]


def test_validate_outline_payload():
    with pytest.raises(ValueError, match="模拟页面结构无效"):
        validate_outline_payload({"title": "x"})  # 缺 sections
    with pytest.raises(ValueError, match="模拟页面结构无效"):
        validate_outline_payload({"title": "x", "sections": [{"blocks": ["b"]}]})  # 区域缺 name
    payload = validate_outline_payload({"title": "x", "sections": [{"name": "n"}]})
    assert payload.title == "x"
    assert payload.sections == [{"name": "n"}]


def test_validate_artifact_html():
    with pytest.raises(ValueError, match="模拟HTML文档不完整"):
        validate_artifact_html("")
    with pytest.raises(ValueError, match="模拟HTML文档不完整"):
        validate_artifact_html("<p>只有片段</p>")  # 缺 <body
    with pytest.raises(ValueError, match="模拟HTML文档不完整"):
        validate_artifact_html("<html><body>缺闭合</body>")  # 缺 </html>
    complete = "<html><body>正文</body></html>"
    assert validate_artifact_html(complete) == complete


def test_validate_payloads_reject_non_mapping():
    # 非 dict 输入触发 Pydantic 构造的 TypeError/ValueError，被映射为「结构无效」。
    with pytest.raises(ValueError, match="模拟计划结构无效"):
        validate_plan_payload(None)
    with pytest.raises(ValueError, match="模拟页面结构无效"):
        validate_outline_payload(None)