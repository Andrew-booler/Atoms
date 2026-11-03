"""阶段级 AI token 用量收集。

用 ContextVar 在单次阶段调用内逐次记录供应商返回的 usage，避免改动
OutputProvider 的接口形状；模拟输出没有 usage 时仍记录一次调用，但所有
token 字段为 None（不伪造 0），由调用方原样落库。
"""
import contextvars
from typing import Any, Dict, List, Optional, Union

UsageLike = Union[Dict[str, Any], object]

_usage: contextvars.ContextVar[Optional[List[Dict[str, Any]]]] = contextvars.ContextVar(
    "studio_ai_usage_entries", default=None
)
_stage: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "studio_ai_usage_stage", default=None
)
_fallbacks: contextvars.ContextVar[List[Dict[str, Any]]] = contextvars.ContextVar(
    "studio_ai_fallbacks", default=[]
)


def _int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _field(usage: UsageLike, name: str) -> Any:
    if isinstance(usage, dict):
        return usage.get(name)
    return getattr(usage, name, None)


def begin_stage(stage: Optional[str] = None) -> contextvars.Token:
    """开始统计一个阶段，返回用于结束统计的 token。"""
    _fallbacks.set([])
    _stage.set(stage)
    return _usage.set([])


def record_fallback(payload: Dict[str, Any]) -> None:
    """记录一次供应商降级；仅在阶段统计开启时生效。"""
    if _usage.get() is None:
        return
    _fallbacks.set([*_fallbacks.get(), payload])


def fallbacks() -> List[Dict[str, Any]]:
    return list(_fallbacks.get())


def record_usage(usage: Optional[UsageLike], *, provider: Optional[str] = None) -> None:
    """记录一次 AI 调用；usage 为 None 时字段全部记 None（模拟输出不伪造数字）。"""
    entries = _usage.get()
    if entries is None:
        return

    resolved_provider = provider
    if resolved_provider is None and usage is not None:
        resolved_provider = _field(usage, "provider")

    entries.append(
        {
            "provider": resolved_provider,
            "prompt_tokens": _int_or_none(_field(usage, "prompt_tokens")) if usage is not None else None,
            "completion_tokens": _int_or_none(_field(usage, "completion_tokens")) if usage is not None else None,
            "reasoning_tokens": _int_or_none(_field(usage, "reasoning_tokens")) if usage is not None else None,
        }
    )


def _sum_field(entries: List[Dict[str, Any]], name: str) -> Optional[int]:
    values = [entry[name] for entry in entries if entry.get(name) is not None]
    return sum(values) if values else None


def finish_stage(token: contextvars.Token) -> Optional[Dict[str, Any]]:
    """结束统计并返回汇总；没有任何调用记录时返回 None。"""
    entries = _usage.get() or []
    stage = _stage.get()
    _usage.reset(token)
    _stage.set(None)
    if not entries:
        return None

    prompt_tokens = _sum_field(entries, "prompt_tokens")
    completion_tokens = _sum_field(entries, "completion_tokens")
    reasoning_tokens = _sum_field(entries, "reasoning_tokens")
    total_tokens: Optional[int] = None
    if prompt_tokens is not None or completion_tokens is not None:
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

    return {
        "stage": stage,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "calls": len(entries),
        "entries": entries,
    }
