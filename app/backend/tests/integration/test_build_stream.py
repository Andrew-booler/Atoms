"""构建终端集成测试：SSE 事件序列、鉴权与多用户隔离。

AI 边界仍由受控提供者返回固定结果（零真实调用）；沙箱不可用时预览事件降级为
preview_ready=False，但事件序列与 done 仍必须完整。
"""
import json

import httpx
from sqlalchemy import func, select

from core.auth import create_access_token
from routers.studio import _plan_request_text
from services import studio_output
from testing import studio_app as host

API = "/api/v1/studio"
REQUIREMENT = "增加备注"


def _sse_events(text: str) -> list[tuple[str, dict]]:
    """解析 SSE 文本；忽略注释心跳（: keep-alive）。"""
    parsed: list[tuple[str, dict]] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        event_type = None
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].lstrip())
        if event_type and data_lines:
            parsed.append((event_type, json.loads("\n".join(data_lines))))
    return parsed


async def _build_fixture(client) -> tuple[int, str, dict]:
    project = (
        await client.post(f"{API}/projects", json={"name": "终端", "description": ""})
    ).json()
    build = await client.post(f"{API}/projects/{project['id']}/builds")
    assert build.status_code == 201
    build_id = build.json()["build_id"]
    plan_summary = _plan_request_text(studio_output.fixture(REQUIREMENT)["plan"])
    outline = studio_output.fixture(REQUIREMENT)["outline"]
    return project["id"], build_id, {"require": REQUIREMENT, "plan_summary": plan_summary, "outline": outline}


async def _run_full_build(client, project_id: int, build_id: str, body: dict) -> None:
    """跑完 plan→outline→artifact，确保事件流在 done 后自然关闭。"""
    plan = await client.post(
        f"{API}/projects/{project_id}/plan?build_id={build_id}",
        json={"requirement": body["require"]},
    )
    assert plan.status_code == 200
    outline = await client.post(
        f"{API}/projects/{project_id}/outline?build_id={build_id}",
        json={"requirement": body["require"], "plan_summary": body["plan_summary"]},
    )
    assert outline.status_code == 200
    artifact = await client.post(
        f"{API}/projects/{project_id}/artifact?build_id={build_id}",
        json={
            "requirement": body["require"],
            "plan_summary": body["plan_summary"],
            "outline": body["outline"],
        },
    )
    assert artifact.status_code == 200


# 集成-B1：三阶段事件按固定顺序落库，且交付事件含文件大小与预览摘要
async def test_build_events_are_persisted_in_order(client):
    project_id, build_id, body = await _build_fixture(client)
    await _run_full_build(client, project_id, build_id, body)

    latest = await client.get(f"{API}/projects/{project_id}/builds/latest")
    assert latest.status_code == 200
    payload = latest.json()
    assert payload["build_id"] == build_id
    events = payload["events"]
    assert [event["type"] for event in events] == [
        "log",
        "stage_started",
        "stage_finished",
        "stage_started",
        "stage_finished",
        "stage_started",
        "stage_finished",
        "file_created",
        "log",
        "done",
    ]
    assert [event["seq"] for event in events] == list(range(1, 11))

    plan_finished = events[2]
    assert plan_finished["stage"] == "plan"
    assert isinstance(plan_finished["data"]["duration_ms"], int)
    # mock 提供者没有 usage 字段，阶段用量应为 None（真实调用时才可能有值）。
    assert plan_finished["data"]["usage"] is None

    created = events[7]
    assert created["data"]["name"] == "index.html"
    assert created["data"]["bytes"] > 0

    log = events[8]["data"]
    assert set(log) >= {"preview_ready", "stdout", "stderr", "files", "port", "preview_url", "reason"}
    assert isinstance(log["files"], list)
    assert events[9]["type"] == "done"

    # 事件里只允许文件元信息，绝不出现页面正文。
    assert "<html" not in json.dumps([event["data"] for event in events], ensure_ascii=False)


# 集成-B2：SSE 流回放历史事件并在 done 后主动关闭
async def test_build_stream_replays_and_closes_after_done(client):
    project_id, build_id, body = await _build_fixture(client)
    await _run_full_build(client, project_id, build_id, body)

    history = await client.get(f"{API}/projects/{project_id}/builds/latest")
    expected = [event["type"] for event in history.json()["events"]]

    stream = await client.get(f"{API}/projects/{project_id}/builds/{build_id}/stream")
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")

    parsed = _sse_events(stream.text)
    assert [event_type for event_type, _ in parsed] == expected
    assert parsed[-1][0] == "done"
    assert parsed[-1][1]["message"] == "构建完成"


# 集成-B3：SSE 未登录返回 401，错误契约形状不变
async def test_build_stream_requires_auth(client):
    project_id, build_id, _ = await _build_fixture(client)
    resp = await client.get(
        f"{API}/projects/{project_id}/builds/{build_id}/stream",
        headers={"Authorization": ""},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_REQUIRED"
    assert resp.json()["message"]


# 集成-B4：跨用户读取构建历史/事件流统一 404
async def test_build_stream_cross_user_is_404(client, other_headers):
    project_id, build_id, _ = await _build_fixture(client)

    stream = await client.get(
        f"{API}/projects/{project_id}/builds/{build_id}/stream",
        headers=other_headers,
    )
    assert stream.status_code == 404
    assert stream.json()["code"] == "RESOURCE_NOT_FOUND"

    latest = await client.get(
        f"{API}/projects/{project_id}/builds/latest", headers=other_headers
    )
    assert latest.status_code == 404
    assert latest.json()["code"] == "RESOURCE_NOT_FOUND"

    start = await client.post(
        f"{API}/projects/{project_id}/builds", headers=other_headers
    )
    assert start.status_code == 404
    assert start.json()["code"] == "RESOURCE_NOT_FOUND"


# 集成-B5：EventSource 场景可用 access_token 查询参数鉴权
async def test_build_stream_accepts_query_token(client):
    project_id, build_id, body = await _build_fixture(client)
    await _run_full_build(client, project_id, build_id, body)
    token = create_access_token({"sub": host.TEST_USER_ID})

    stream = await client.get(
        f"{API}/projects/{project_id}/builds/{build_id}/stream?access_token={token}",
        headers={"Authorization": ""},
    )
    assert stream.status_code == 200
    assert "event: stage_finished" in stream.text
    assert "event: done" in stream.text


# 集成-B6：阶段失败写入 error 事件，message 为可读中文而非错误码
async def test_build_error_event_carries_chinese_message(client):
    project_id, build_id, _ = await _build_fixture(client)
    await client.post("/__test/fault", json={"stage": "artifact", "mode": "invalid", "remaining": 1})

    resp = await client.post(
        f"{API}/projects/{project_id}/artifact?build_id={build_id}",
        json={
            "requirement": REQUIREMENT,
            "plan_summary": "x",
            "outline": {"title": "t", "sections": []},
        },
    )
    assert resp.status_code == 502

    latest = await client.get(f"{API}/projects/{project_id}/builds/latest")
    events = latest.json()["events"]
    error_event = events[-1]
    assert error_event["type"] == "error"
    assert error_event["message"] == "生成的页面内容无效，请重新生成。"
    assert error_event["data"]["code"] == "STUDIO_ARTIFACT_INVALID"
    assert error_event["data"]["stage"] == "artifact"


# 集成-B7：其他项目的 build_id 不得借用（404）
async def test_build_id_must_belong_to_project(client):
    project_a, build_a, _ = await _build_fixture(client)
    project_b = (
        await client.post(f"{API}/projects", json={"name": "乙", "description": ""})
    ).json()

    resp = await client.post(
        f"{API}/projects/{project_b['id']}/plan?build_id={build_a}",
        json={"requirement": REQUIREMENT},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "RESOURCE_NOT_FOUND"

    count = await client.get(f"{API}/projects/{project_a}/builds/latest")
    assert count.status_code == 200


# 集成-B8：最新构建查询按 user_id 过滤，不串用户
async def test_latest_build_filters_by_user(client, other_headers):
    project_id, build_id, _ = await _build_fixture(client)

    async with host.engine.connect() as conn:
        own = await conn.scalar(
            select(func.count()).select_from(host.BuildEvent.__table__).where(
                host.BuildEvent.user_id == host.TEST_USER_ID
            )
        )
        foreign = await conn.scalar(
            select(func.count()).select_from(host.BuildEvent.__table__).where(
                host.BuildEvent.user_id == host.OTHER_USER_ID
            )
        )
    assert own >= 1
    assert foreign == 0

    # 另一个用户对同一项目不可见
    resp = await client.get(
        f"{API}/projects/{project_id}/builds/latest", headers=other_headers
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "RESOURCE_NOT_FOUND"


async def test_unauthenticated_client_gets_401_on_history():
    headers = {"Authorization": ""}
    transport = httpx.ASGITransport(app=host.app)
    async with host.lifespan(host.app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", headers=headers
        ) as ac:
            resp = await ac.get(f"{API}/projects/1/builds/latest")
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_REQUIRED"
