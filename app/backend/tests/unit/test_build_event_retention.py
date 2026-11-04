"""构建事件保留策略的纯逻辑单元测试。"""
from services import build_events


def test_builds_to_delete_keeps_newest_n():
    ids = ["b4", "b3", "b2", "b1"]
    assert build_events.builds_to_delete(ids, 2) == ["b2", "b1"]


def test_builds_to_delete_keeps_all_when_fewer_than_limit():
    assert build_events.builds_to_delete(["b2", "b1"], 5) == []


def test_builds_to_delete_deduplicates_and_ignores_empty():
    assert build_events.builds_to_delete(["b1", "b1", "", None, "b2"], 1) == ["b2"]


def test_builds_to_delete_always_keeps_at_least_one():
    assert build_events.builds_to_delete(["b2", "b1"], 0) == ["b1"]


def test_configured_keep_builds_reads_env(monkeypatch):
    monkeypatch.setenv("APP_BUILD_EVENT_KEEP_BUILDS", "5")
    assert build_events.configured_keep_builds() == 5


def test_configured_keep_builds_falls_back_on_invalid(monkeypatch):
    monkeypatch.setenv("APP_BUILD_EVENT_KEEP_BUILDS", "not-a-number")
    assert build_events.configured_keep_builds() == build_events.DEFAULT_KEEP_BUILDS
