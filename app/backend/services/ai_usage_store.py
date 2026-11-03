"""AI 用量落库与聚合。

产品内统计口径：每次调用一行（见 models.ai_usage），按用户聚合
今日 / 近 7 天 / 累计，并按 provider 分列。与 docs/AI额度使用记录.md
里的“免费额度余量台账”是两套数据：这里统计应用内真实调用累计，
那里记录供应商侧免费额度的剩余量。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_usage import AiUsageRecord

UNKNOWN_PROVIDER = "unknown"


def summarize(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """对一组调用记录求 token 汇总；全部缺失时返回 None 而不是 0。"""
    items = list(rows)
    calls = len(items)

    def _sum(name: str) -> Optional[int]:
        values = [item[name] for item in items if item.get(name) is not None]
        return sum(values) if values else None

    prompt_tokens = _sum("prompt_tokens")
    completion_tokens = _sum("completion_tokens")
    reasoning_tokens = _sum("reasoning_tokens")
    total_tokens: Optional[int] = None
    if prompt_tokens is not None or completion_tokens is not None:
        # reasoning 属于 completion 的一部分，避免重复计入总量。
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

    return {
        "calls": calls,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "has_data": calls > 0,
    }


def provider_breakdown(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 provider 分列；provider 缺失的记录归入 unknown。"""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        name = row.get("provider") or UNKNOWN_PROVIDER
        groups.setdefault(name, []).append(row)
    result = [
        {"provider": name, **summarize(items)} for name, items in groups.items()
    ]
    result.sort(key=lambda item: (-item["calls"], item["provider"]))
    return result


def _aware(value: Optional[datetime], tzinfo) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=tzinfo)


def split_windows(
    rows: Iterable[Dict[str, Any]], now: datetime
) -> Dict[str, List[Dict[str, Any]]]:
    """按自然日切分：今日、近 7 天（含今日，共 7 个自然日）、累计。"""
    tzinfo = now.tzinfo
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_start = today_start - timedelta(days=6)

    today_rows: List[Dict[str, Any]] = []
    recent_rows: List[Dict[str, Any]] = []
    all_rows: List[Dict[str, Any]] = []
    for row in rows:
        created = _aware(row.get("created_at"), tzinfo)
        all_rows.append(row)
        if created is None:
            continue
        if created >= seven_start:
            recent_rows.append(row)
        if created >= today_start:
            today_rows.append(row)
    return {"today": today_rows, "last_7_days": recent_rows, "total": all_rows}


def _latest_build(rows: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    build_rows = [row for row in rows if row.get("build_id")]
    if not build_rows:
        return None
    tzinfo = datetime.now().astimezone().tzinfo

    def _stamp(row: Dict[str, Any]) -> float:
        created = _aware(row.get("created_at"), tzinfo)
        return created.timestamp() if created else 0.0

    build_rows.sort(key=_stamp, reverse=True)
    build_id = build_rows[0]["build_id"]
    items = [row for row in build_rows if row["build_id"] == build_id]
    recorded_at = max(
        (_aware(row.get("created_at"), tzinfo) for row in items if row.get("created_at")),
        default=None,
    )
    return {
        "build_id": build_id,
        "recorded_at": recorded_at,
        "totals": summarize(items),
        "providers": provider_breakdown(items),
    }


async def fetch_rows(db: AsyncSession, *, user_id: str) -> List[Dict[str, Any]]:
    """读取该用户的全部调用记录（按 user_id 强制隔离）。"""
    result = await db.execute(
        select(
            AiUsageRecord.build_id,
            AiUsageRecord.stage,
            AiUsageRecord.provider,
            AiUsageRecord.prompt_tokens,
            AiUsageRecord.completion_tokens,
            AiUsageRecord.reasoning_tokens,
            AiUsageRecord.created_at,
        ).where(AiUsageRecord.user_id == user_id)
    )
    return [dict(row._mapping) for row in result]


async def collect(
    db: AsyncSession, *, user_id: str, now: Optional[datetime] = None
) -> Dict[str, Any]:
    """按用户聚合今日 / 近 7 天 / 累计 + provider 分布 + 最近一次构建。"""
    current = now or datetime.now().astimezone()
    rows = await fetch_rows(db, user_id=user_id)
    windows = split_windows(rows, current)
    payload: Dict[str, Any] = {
        "generated_at": current,
        "latest_build": _latest_build(rows),
    }
    for key, items in windows.items():
        payload[key] = {
            "totals": summarize(items),
            "providers": provider_breakdown(items),
        }
    return payload


async def save_calls(
    db: AsyncSession,
    *,
    user_id: str,
    build_id: Optional[str],
    stage: Optional[str],
    entries: Iterable[Dict[str, Any]],
) -> int:
    """把阶段内逐次调用记录落库；由调用方负责提交事务。"""
    rows = [
        AiUsageRecord(
            user_id=user_id,
            build_id=build_id,
            stage=stage,
            provider=entry.get("provider"),
            prompt_tokens=entry.get("prompt_tokens"),
            completion_tokens=entry.get("completion_tokens"),
            reasoning_tokens=entry.get("reasoning_tokens"),
        )
        for entry in entries
    ]
    if not rows:
        return 0
    db.add_all(rows)
    await db.flush()
    return len(rows)
