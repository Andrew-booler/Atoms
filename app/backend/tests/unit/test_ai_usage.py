"""阶段级 token 用量收集器单元测试。"""
from types import SimpleNamespace

from services import ai_usage


def test_begin_and_finish_without_usage_returns_none():
    token = ai_usage.begin_stage()
    assert ai_usage.finish_stage(token) is None


def test_record_usage_accepts_dict_and_object():
    token = ai_usage.begin_stage()
    ai_usage.record_usage({"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})
    ai_usage.record_usage(SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3))
    usage = ai_usage.finish_stage(token)
    assert usage == {
        "prompt_tokens": 11,
        "completion_tokens": 22,
        "total_tokens": 33,
        "calls": 2,
    }


def test_record_usage_outside_stage_is_ignored():
    ai_usage.record_usage({"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10})
    token = ai_usage.begin_stage()
    assert ai_usage.finish_stage(token) is None


def test_stage_scope_does_not_leak_between_stages():
    first = ai_usage.begin_stage()
    ai_usage.record_usage({"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    assert ai_usage.finish_stage(first)["total_tokens"] == 2

    second = ai_usage.begin_stage()
    assert ai_usage.finish_stage(second) is None
