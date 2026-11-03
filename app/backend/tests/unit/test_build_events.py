"""构建事件服务单元测试：序列化、SSE 帧与类型校验（不依赖数据库）。"""
import json
from types import SimpleNamespace

import pytest

from services import build_events
from services.build_events import EVENT_TYPES


def _row(**overrides):
    row = SimpleNamespace(
        seq=1,
        type="log",
        stage=None,
        message="hello",
        data='{"port": 8080}',
        created_at=None,
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def test_serialize_event_returns_dict_payload():
    payload = build_events.serialize_event(_row(type="log", message="已就绪"))
    assert payload["seq"] == 1
    assert payload["type"] == "log"
    assert payload["data"] == {"port": 8080}
    assert payload["created_at"] is None


def test_serialize_event_tolerates_broken_json():
    payload = build_events.serialize_event(_row(data="not-json"))
    assert payload["data"] == {}


def test_sse_frame_contains_event_and_json_data():
    frame = build_events.sse_frame(_row(type="stage_started", stage="plan"))
    assert frame.startswith("id: 1\n")
    assert "event: stage_started\n" in frame
    assert frame.endswith("\n\n")
    body = json.loads(frame.split("data: ", 1)[1])
    assert body["stage"] == "plan"


def test_event_types_are_fixed():
    assert EVENT_TYPES == (
        "stage_started",
        "stage_finished",
        "file_created",
        "log",
        "error",
        "done",
    )
    assert build_events.TERMINAL_TYPES == ("error", "done")


@pytest.mark.asyncio
async def test_append_event_rejects_unknown_type_before_db():
    with pytest.raises(ValueError, match="未知的构建事件类型"):
        await build_events.append_event(
            None,  # type: ignore[arg-type]
            user_id="u1",
            project_id=1,
            build_id="b1",
            type="unknown",
        )
