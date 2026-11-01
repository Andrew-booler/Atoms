"""Studio 阶段输入的结构校验纯函数，供计划、结构与 HTML 三分支复用并单测。"""
from typing import Any

from schemas.studio import OutlinePayload, PlanPayload


def validate_plan_payload(raw: Any) -> PlanPayload:
    try:
        payload = PlanPayload(**raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("模拟计划结构无效") from exc
    if not payload.steps or any(not step.get("title") for step in payload.steps):
        raise ValueError("模拟计划结构无效")
    return payload


def validate_outline_payload(raw: Any) -> OutlinePayload:
    try:
        payload = OutlinePayload(**raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("模拟页面结构无效") from exc
    if not payload.sections or any(not section.get("name") for section in payload.sections):
        raise ValueError("模拟页面结构无效")
    return payload


def validate_artifact_html(html: str) -> str:
    if not html.strip() or "<body" not in html.lower() or "</html>" not in html.lower():
        raise ValueError("模拟HTML文档不完整")
    return html