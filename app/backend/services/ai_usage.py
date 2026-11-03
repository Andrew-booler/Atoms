"""阶段级 AI token 用量收集。

用 ContextVar 在单次阶段调用内累加供应商返回的 usage，避免改动
OutputProvider 的接口形状；模拟输出没有 usage 时返回 None。
"""
import contextvars
from typing import Any, Dict, Optional

Tracker = Dict[str, int]
_usage: contextvars.ContextVar[Optional[Tracker]] = contextvars.ContextVar(
    "studio_ai_usage", default=None
)


def begin_stage() -> contextvars.Token:
    """开始统计一个阶段，返回用于结束统计的 token。"""
    return _usage.set(
        {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
    )


def record_usage(usage: Any) -> None:
    """累加一次模型调用的 usage；usage 可为 dict 或含同名字段的对象。"""
    current = _usage.get()
    if current is None or usage is None:
        return

    def _field(name: str) -> int:
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, 0)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    current["prompt_tokens"] += _field("prompt_tokens")
    current["completion_tokens"] += _field("completion_tokens")
    current["total_tokens"] += _field("total_tokens")
    current["calls"] += 1


def finish_stage(token: contextvars.Token) -> Optional[Tracker]:
    """结束统计并返回汇总；没有任何有效 usage 时返回 None。"""
    current = _usage.get()
    _usage.reset(token)
    if current is None or current["calls"] <= 0:
        return None
    return dict(current)
