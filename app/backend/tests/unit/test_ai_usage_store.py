"""用量聚合的纯函数单元测试：口径、空数据与时间窗边界。"""
from datetime import datetime, timedelta, timezone

from services import ai_usage_store


def _row(provider=None, prompt=None, completion=None, reasoning=None, created_at=None, build_id=None):
    return {
        "provider": provider,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "reasoning_tokens": reasoning,
        "created_at": created_at,
        "build_id": build_id,
    }


def test_summarize_empty_returns_no_data_not_zero():
    totals = ai_usage_store.summarize([])
    assert totals["calls"] == 0
    assert totals["prompt_tokens"] is None
    assert totals["completion_tokens"] is None
    assert totals["reasoning_tokens"] is None
    assert totals["total_tokens"] is None
    assert totals["has_data"] is False


def test_summarize_counts_calls_with_null_usage_without_faking_tokens():
    totals = ai_usage_store.summarize([_row(provider="mock"), _row(provider="mock")])
    assert totals["calls"] == 2
    assert totals["total_tokens"] is None
    assert totals["has_data"] is True


def test_summarize_sums_tokens_and_reasoning():
    totals = ai_usage_store.summarize(
        [
            _row(provider="openai", prompt=10, completion=20, reasoning=5),
            _row(provider="aliyun", prompt=1, completion=2, reasoning=None),
        ]
    )
    assert totals["prompt_tokens"] == 11
    assert totals["completion_tokens"] == 22
    assert totals["reasoning_tokens"] == 5
    assert totals["total_tokens"] == 33
    assert totals["calls"] == 2


def test_provider_breakdown_groups_and_labels_unknown():
    rows = [
        _row(provider="openai", prompt=10, completion=20),
        _row(provider="openai", prompt=1, completion=2),
        _row(provider=None, prompt=5, completion=5),
    ]
    breakdown = ai_usage_store.provider_breakdown(rows)
    by_name = {item["provider"]: item for item in breakdown}
    assert by_name["openai"]["calls"] == 2
    assert by_name["openai"]["total_tokens"] == 33
    assert by_name["unknown"]["calls"] == 1
    # 按调用次数降序，openai 在 unknown 之前
    assert breakdown[0]["provider"] == "openai"


def test_split_windows_uses_calendar_day_boundaries():
    tz = timezone(timedelta(hours=8))
    now = datetime(2026, 11, 4, 12, 0, tzinfo=tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = [
        _row(created_at=today_start + timedelta(hours=9)),
        _row(created_at=today_start - timedelta(days=6)),  # 近 7 天起点，含
        _row(created_at=today_start - timedelta(days=7)),  # 窗口外
        _row(created_at=today_start - timedelta(days=8)),  # 窗口外
    ]
    windows = ai_usage_store.split_windows(rows, now)
    assert len(windows["today"]) == 1
    assert len(windows["last_7_days"]) == 2
    assert len(windows["total"]) == 4


def test_latest_build_prefers_most_recent_record():
    tz = timezone(timedelta(hours=8))
    now = datetime(2026, 11, 4, 12, 0, tzinfo=tz)
    rows = [
        _row(provider="aliyun", prompt=10, completion=10, created_at=now, build_id="build-new"),
        _row(provider="openai", prompt=1, completion=1, created_at=now - timedelta(hours=1), build_id="build-old"),
    ]
    latest = ai_usage_store._latest_build(rows)
    assert latest is not None
    assert latest["build_id"] == "build-new"
    assert latest["totals"]["total_tokens"] == 20


def test_latest_build_without_builds_is_none():
    assert ai_usage_store._latest_build([_row(provider="mock")]) is None
