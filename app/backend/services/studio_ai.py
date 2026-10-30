"""AI 编排层。

把「需求 → 结构化计划 → 界面结构 → 可运行产物」拆成三个可替换的步骤。
所有模型调用都在服务端通过 AIHubService 完成，前端不接触模型名与密钥；
切换模型只需修改 MODEL_PROFILES 中的 id。
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from schemas.aihub import ChatMessage, GenTxtRequest
from services.aihub import AIHubService

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = "balanced"

MODEL_PROFILES: Dict[str, Dict[str, str]] = {
    "balanced": {
        "id": "gpt-5.5",
        "label": "Balanced",
        "hint": "通用的高质量文本模型，速度与效果均衡",
    },
    "fast": {
        "id": "deepseek-v4-flash",
        "label": "Fast",
        "hint": "速度最快、成本最低，适合小步快速迭代",
    },
    "quality": {
        "id": "claude-opus-5",
        "label": "Quality",
        "hint": "长上下文与复杂界面还原能力更强",
    },
}

PROMPT_SYSTEM = (
    "你是一名资深前端产品工程师，擅长把模糊的一句话需求拆解成可执行的原型开发计划。"
    "你只输出 JSON，不输出任何解释性文字。"
)

ARTIFACT_SYSTEM = """你是资深前端工程师，负责把产品需求实现成一个可以直接运行的单文件 HTML 应用。

硬性规则：
1. 只输出一个完整 HTML 文档，从 <!DOCTYPE html> 开始、到 </html> 结束；不要 Markdown 代码块，不要任何解释。
2. 禁止外部资源：不得引用 CDN、外链字体、外链图片、外部 JS/CSS。样式全部写进 <style>，脚本全部写进 <script>。
3. 用内联 SVG、CSS 渐变或 emoji 表达图形，不要使用 <img src="http...">。
4. 必须实现需求里的核心交互（表单能提交、按钮有反馈、状态会更新、数据有增减），并使用有意义的示例数据。
5. 不允许出现「TODO」「占位」「示例文字」这类未完成痕迹，不要写 tbd。
6. 语义化标签 + 响应式（≤820px 收成单列）+ 可访问性（焦点可见、对比度足够）。
7. 视觉克制：浅色底、充足留白、清晰的层级，主色只用于关键动作，不要霓虹渐变或发光卡片。
8. 输出控制在 400 行以内，代码保持可读。
"""


def _profile(profile: Optional[str]) -> Dict[str, str]:
    key = (profile or DEFAULT_PROFILE).strip()
    return MODEL_PROFILES.get(key, MODEL_PROFILES[DEFAULT_PROFILE])


def resolve_model(profile: Optional[str] = None) -> str:
    return _profile(profile)["id"]


def available_models() -> List[Dict[str, str]]:
    return [
        {"key": key, "model": value["id"], "label": value["label"], "hint": value["hint"]}
        for key, value in MODEL_PROFILES.items()
    ]


def _extract_json_block(text: str) -> str:
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    return raw


def sanitize_html(raw: str) -> str:
    """从模型输出中取出完整 HTML 文档。"""
    text = raw.strip()
    fence = re.search(r"```(?:html)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    lower = text.lower()
    start = lower.find("<!doctype")
    if start < 0:
        start = lower.find("<html")
    end = lower.rfind("</html>")
    if start < 0 or end < 0:
        raise ValueError("模型输出不是完整的 HTML 文档")

    document = text[start : end + len("</html>")].strip()
    if "<body" not in document.lower():
        raise ValueError("模型输出缺少 body")
    return document


async def _gentxt(
    system: str,
    user: str,
    *,
    model: str,
    max_tokens: int,
    temperature: float = 0.6,
) -> str:
    service = AIHubService()
    request = GenTxtRequest(
        messages=[
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ],
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    response = await service.gentxt(request)
    return (response.content or "").strip()


async def _gentxt_json(
    system: str,
    user: str,
    *,
    model: str,
    max_tokens: int,
    required: List[str],
    temperature: float = 0.6,
) -> Dict[str, Any]:
    raw = await _gentxt(
        system, user, model=model, max_tokens=max_tokens, temperature=temperature
    )
    payload_text = _extract_json_block(raw)

    payload: Optional[Dict[str, Any]] = None
    try:
        parsed = json.loads(payload_text)
        if isinstance(parsed, dict):
            payload = parsed
    except json.JSONDecodeError:
        payload = None

    if payload is None or any(field not in payload for field in required):
        repaired = await _gentxt(
            "你只输出合法 JSON，字段齐全，不要解释。修复下面这段内容，返回合法 JSON。",
            payload_text,
            model=model,
            max_tokens=max_tokens,
            temperature=0,
        )
        try:
            parsed = json.loads(_extract_json_block(repaired))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="AI 输出解析失败，请重试") from exc
        if not isinstance(parsed, dict) or any(field not in parsed for field in required):
            raise HTTPException(status_code=502, detail="AI 输出字段不完整，请重试")
        payload = parsed

    return payload


def _normalize_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    steps: List[Dict[str, str]] = []
    for item in payload.get("steps") or []:
        if isinstance(item, str):
            steps.append({"title": item, "detail": ""})
        elif isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or "").strip()
            if not title:
                continue
            steps.append({"title": title, "detail": str(item.get("detail") or "").strip()})

    files: List[Dict[str, str]] = []
    for item in payload.get("files") or []:
        if isinstance(item, str):
            files.append({"path": item, "purpose": ""})
        elif isinstance(item, dict):
            path = str(item.get("path") or item.get("name") or "").strip()
            if not path:
                continue
            files.append({"path": path, "purpose": str(item.get("purpose") or "").strip()})

    stack = [str(item).strip() for item in (payload.get("stack") or []) if str(item).strip()]

    return {
        "summary": str(payload.get("summary") or "").strip() or "根据需求生成可运行原型",
        "stack": stack[:6],
        "steps": steps[:8] or [{"title": "生成可运行原型", "detail": ""}],
        "files": files[:8],
    }


def _normalize_outline(payload: Dict[str, Any]) -> Dict[str, Any]:
    sections: List[Dict[str, Any]] = []
    for item in payload.get("sections") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("title") or "").strip()
        if not name:
            continue
        blocks = [str(block).strip() for block in (item.get("blocks") or []) if str(block).strip()]
        sections.append({"name": name, "blocks": blocks[:6]})

    seed_data = [str(item).strip() for item in (payload.get("seed_data") or []) if str(item).strip()]
    interactions = [
        str(item).strip() for item in (payload.get("interactions") or []) if str(item).strip()
    ]

    return {
        "title": str(payload.get("title") or "Prototype").strip(),
        "sections": sections[:8],
        "interactions": interactions[:8],
        "seed_data": seed_data[:10],
    }


async def generate_plan(
    requirement: str,
    *,
    project_name: str,
    context: str = "",
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    model = resolve_model(profile)
    user = f"""把下面这条需求拆解成可执行的单文件原型开发计划。

项目名：{project_name}
需求：{requirement}
已有上下文：{context or "无，这是第一个版本"}

返回 JSON，字段：
- summary: 一句话说明这次要交付什么（中文，≤40 字）
- stack: 实现要点的短标签数组（2-4 个）
- steps: 数组，元素为 {{"title": 步骤名（≤12 字）, "detail": 该步骤具体做什么（≤40 字）}}
- files: 数组，元素为 {{"path": 计划产出的文件路径, "purpose": 该文件职责（≤24 字）}}

要求：steps 为 3-5 个，必须是实现该需求真正需要的步骤，不要写“需求分析”这种空话。"""
    payload = await _gentxt_json(
        PROMPT_SYSTEM, user, model=model, max_tokens=1600, required=["summary", "steps"]
    )
    return _normalize_plan(payload)


async def generate_outline(
    requirement: str,
    plan: Dict[str, Any],
    *,
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    model = resolve_model(profile)
    user = f"""根据需求和计划，设计这个原型的界面结构与示例数据。

需求：{requirement}
计划摘要：{plan.get("summary", "")}
计划步骤：{json.dumps(plan.get("steps", []), ensure_ascii=False)}

返回 JSON，字段：
- title: 产品内显示的应用名（≤14 字）
- sections: 数组，元素为 {{"name": 区块名, "blocks": [该区块包含的具体内容元素，2-5 个]}}
- interactions: 数组，列出必须真正可用的交互（如“新增一条记录后列表立即更新”）
- seed_data: 数组，3-8 条可直接展示的真实示例数据文案

要求：sections 为 3-5 个；内容要具体，能直接写成界面，不要抽象占位。"""
    payload = await _gentxt_json(
        PROMPT_SYSTEM, user, model=model, max_tokens=2200, required=["title", "sections"]
    )
    return _normalize_outline(payload)


async def generate_artifact(
    requirement: str,
    plan: Dict[str, Any],
    outline: Dict[str, Any],
    *,
    profile: Optional[str] = None,
) -> str:
    model = resolve_model(profile)
    user = f"""实现下面这个原型，输出完整的单文件 HTML 应用。

需求：{requirement}
计划摘要：{plan.get("summary", "")}
应用名：{outline.get("title", "Prototype")}
界面结构：{json.dumps(outline.get("sections", []), ensure_ascii=False)}
必须可用的交互：{json.dumps(outline.get("interactions", []), ensure_ascii=False)}
示例数据：{json.dumps(outline.get("seed_data", []), ensure_ascii=False)}

界面语言与需求语言保持一致。现在直接输出 HTML。"""

    raw = await _gentxt(
        ARTIFACT_SYSTEM, user, model=model, max_tokens=6144, temperature=0.7
    )
    try:
        return sanitize_html(raw)
    except ValueError:
        repaired = await _gentxt(
            ARTIFACT_SYSTEM,
            "上一次输出不是完整 HTML。请重新输出完整文档，从 <!DOCTYPE html> 开始、到 </html> 结束，只输出 HTML。\n\n需求："
            + requirement,
            model=model,
            max_tokens=6144,
            temperature=0.4,
        )
        try:
            return sanitize_html(repaired)
        except ValueError as exc:
            raise HTTPException(
                status_code=502, detail="生成的产物不完整，请重试或换一个模型"
            ) from exc
