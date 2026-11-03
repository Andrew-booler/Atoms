"""AI 编排层。

把「需求 → 结构化计划 → 界面结构 → 可运行产物」拆成三个可替换的步骤。
所有模型调用都在服务端通过 AIHubService 完成，前端不接触模型名与密钥；
切换模型只需修改 MODEL_PROFILES 中的 id。
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from core import error_codes
from core.exceptions import ProviderError
from schemas.aihub import ChatMessage, GenTxtRequest
from services import ai_usage
from services.aihub import AI_MAX_RETRIES, AIHubService, _backoff_seconds, _env_bool, _env_int

#: 各阶段结构化输出失败时使用的错误码：(通用失败, 内容无效)。
_STAGE_ERROR_CODES: Dict[str, tuple[str, str]] = {
    "plan": (error_codes.STUDIO_PLAN_FAILED, error_codes.STUDIO_PLAN_INVALID),
    "outline": (error_codes.STUDIO_OUTLINE_FAILED, error_codes.STUDIO_OUTLINE_INVALID),
}

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = "balanced"

MODEL_PROFILES: Dict[str, Dict[str, str]] = {
    "balanced": {
        "id": "qwen3.8-flash",
        "label": "Balanced",
        "hint": "阿里百炼 Qwen3.8-Flash，主选（失败自动降级到方舟/智谱）",
    },
    "fast": {
        "id": "qwen3.8-flash",
        "label": "Fast",
        "hint": "阿里百炼 Qwen3.8-Flash，轻量快速（失败自动降级）",
    },
    "quality": {
        "id": "qwen3.8-flash",
        "label": "Quality",
        "hint": "阿里百炼 Qwen3.8-Flash，长上下文还原（失败自动降级）",
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


# 各阶段输出预算：可用环境变量覆盖，避免硬编码；plan/outline 保持原值，
# artifact 需要容纳完整单文件 HTML；请求总量另按思考开关换算（见 _stage_request_tokens）。
STAGE_MAX_TOKENS_DEFAULTS: Dict[str, int] = {"plan": 1600, "outline": 2200, "artifact": 6144}


def _stage_max_tokens(stage: str) -> int:
    """阶段可见正文预算（不含思考与余量）。"""
    raw = os.environ.get(f"APP_STUDIO_{stage.upper()}_MAX_TOKENS")
    if raw and raw.strip():
        try:
            return int(raw)
        except ValueError:
            pass
    return STAGE_MAX_TOKENS_DEFAULTS[stage]


#: 请求总量余量：覆盖模型附加开销，避免正文恰好触顶。
OUTPUT_TOKEN_MARGIN = 1024
THINKING_BUDGET_DEFAULT = 2048


def _stage_request_tokens(stage: str) -> int:
    """按是否开启思考换算 max_completion_tokens 请求总量。

    开启思考 = 可见正文 + thinking_budget + 余量；关闭思考 = 可见正文 + 余量。
    仅百炼的 thinking_budget 生效，但该总量对两家供应商都安全（都包含思考）。
    """
    visible = _stage_max_tokens(stage)
    if _env_bool("APP_AI_ENABLE_THINKING", False):
        budget = _env_int("APP_STUDIO_THINKING_BUDGET", THINKING_BUDGET_DEFAULT) or THINKING_BUDGET_DEFAULT
        return visible + budget + OUTPUT_TOKEN_MARGIN
    return visible + OUTPUT_TOKEN_MARGIN


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
    max_completion_tokens: int,
    temperature: float = 0.6,
) -> str:
    service = AIHubService()
    request = GenTxtRequest(
        messages=[
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ],
        model=model,
        max_completion_tokens=max_completion_tokens,
        temperature=temperature,
    )
    # 免费模型偶发返回空响应，视为瞬时失败并按指数退避重试。
    for attempt in range(AI_MAX_RETRIES + 1):
        response = await service.gentxt(request)
        # 阶段级 token 用量：模拟提供者没有 usage 时不会累加，最终为 None。
        ai_usage.record_usage(getattr(response, "usage", None))
        content = (response.content or "").strip()
        if content:
            return content
        delay = _backoff_seconds(attempt)
        logger.warning(
            "AI 返回空响应，第 %d/%d 次退避重试，等待 %.2f 秒",
            attempt + 1, AI_MAX_RETRIES, delay,
        )
        await asyncio.sleep(delay)
    return ""


async def _gentxt_json(
    system: str,
    user: str,
    *,
    stage: str,
    model: str,
    max_completion_tokens: int,
    required: List[str],
    temperature: float = 0.6,
) -> Dict[str, Any]:
    failure_code, invalid_code = _STAGE_ERROR_CODES[stage]
    raw = await _gentxt(
        system, user, model=model, max_completion_tokens=max_completion_tokens, temperature=temperature
    )
    payload_text = _extract_json_block(raw)
    if not payload_text.strip():
        raise ProviderError(failure_code, details={"stage": stage, "reason": "empty_response"})

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
            max_completion_tokens=max_completion_tokens,
            temperature=0,
        )
        try:
            parsed = json.loads(_extract_json_block(repaired))
        except json.JSONDecodeError as exc:
            raise ProviderError(
                invalid_code, details={"stage": stage, "reason": "json_parse_failed"}
            ) from exc
        if not isinstance(parsed, dict) or any(field not in parsed for field in required):
            raise ProviderError(
                invalid_code, details={"stage": stage, "reason": "missing_fields"}
            )
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
        PROMPT_SYSTEM, user, stage="plan", model=model,
        max_completion_tokens=_stage_request_tokens("plan"), required=["summary", "steps"],
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
        PROMPT_SYSTEM, user, stage="outline", model=model,
        max_completion_tokens=_stage_request_tokens("outline"), required=["title", "sections"],
    )
    return _normalize_outline(payload)


async def generate_artifact(
    requirement: str,
    plan: Dict[str, Any],
    outline: Dict[str, Any],
    *,
    profile: Optional[str] = None,
    context: Optional[str] = None,
) -> str:
    model = resolve_model(profile)
    context_block = ""
    if context:
        context_block = (
            "\n需要在其基础上修改的现有 HTML（保持单文件、无外部依赖）：\n"
            f"{context}\n"
        )
    user = f"""实现下面这个原型，输出完整的单文件 HTML 应用。

需求：{requirement}
计划摘要：{plan.get("summary", "")}
应用名：{outline.get("title", "Prototype")}
界面结构：{json.dumps(outline.get("sections", []), ensure_ascii=False)}
必须可用的交互：{json.dumps(outline.get("interactions", []), ensure_ascii=False)}
示例数据：{json.dumps(outline.get("seed_data", []), ensure_ascii=False)}
{context_block}
界面语言与需求语言保持一致。现在直接输出 HTML。"""

    raw = await _gentxt(
        ARTIFACT_SYSTEM, user, model=model,
        max_completion_tokens=_stage_request_tokens("artifact"), temperature=0.7,
    )
    try:
        return sanitize_html(raw)
    except ValueError:
        repaired = await _gentxt(
            ARTIFACT_SYSTEM,
            "上一次输出不是完整 HTML。请重新输出完整文档，从 <!DOCTYPE html> 开始、到 </html> 结束，只输出 HTML。\n\n需求："
            + requirement,
            model=model,
            max_completion_tokens=_stage_request_tokens("artifact"),
            temperature=0.4,
        )
        try:
            return sanitize_html(repaired)
        except ValueError as exc:
            raise ProviderError(
                error_codes.STUDIO_ARTIFACT_INVALID,
                details={"stage": "artifact", "reason": "invalid_html"},
            ) from exc
