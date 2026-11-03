"""阶段级 token 用量收集器单元测试。"""
from types import SimpleNamespace

from services import ai_usage


def test_begin_and_finish_without_usage_returns_none():
    token = ai_usage.begin_stage()
    assert ai_usage.finish_stage(token) is None


def test_record_usage_accepts_dict_and_object():
    token = ai_usage.begin_stage("plan")
    ai_usage.record_usage({"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})
    ai_usage.record_usage(SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3))
    usage = ai_usage.finish_stage(token)
    assert usage["stage"] == "plan"
    assert usage["prompt_tokens"] == 11
    assert usage["completion_tokens"] == 22
    assert usage["total_tokens"] == 33
    assert usage["reasoning_tokens"] is None
    assert usage["calls"] == 2
    assert usage["entries"] == [
        {"provider": None, "prompt_tokens": 10, "completion_tokens": 20, "reasoning_tokens": None},
        {"provider": None, "prompt_tokens": 1, "completion_tokens": 2, "reasoning_tokens": None},
    ]


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


def test_provider_and_reasoning_tokens_are_kept_per_call():
    token = ai_usage.begin_stage("artifact")
    ai_usage.record_usage(
        {
            "provider": "openai",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "reasoning_tokens": 20,
            "total_tokens": 150,
        }
    )
    usage = ai_usage.finish_stage(token)
    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 50
    assert usage["reasoning_tokens"] == 20
    assert usage["total_tokens"] == 150
    assert usage["entries"][0]["provider"] == "openai"
    assert usage["entries"][0]["reasoning_tokens"] == 20


def test_mock_usage_is_null_and_never_fabricated():
    token = ai_usage.begin_stage("outline")
    ai_usage.record_usage(None, provider="mock")
    usage = ai_usage.finish_stage(token)
    assert usage["calls"] == 1
    assert usage["prompt_tokens"] is None
    assert usage["completion_tokens"] is None
    assert usage["reasoning_tokens"] is None
    assert usage["total_tokens"] is None
    assert usage["entries"] == [
        {"provider": "mock", "prompt_tokens": None, "completion_tokens": None, "reasoning_tokens": None}
    ]
