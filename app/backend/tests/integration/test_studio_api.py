"""后端接口集成测试：真实路由 + 真实 SQLAlchemy 事务 + 真实 PostgreSQL。

AI 边界由测试宿主的受控提供者返回固定结果；使用独立 schema（见 integration/conftest.py），
逐例 /__test/reset 归零。每条用例标题标注被测路由函数。
"""
from sqlalchemy import func, select

from routers.studio import _plan_request_text
from services import studio_output
from testing import studio_app as host

API = "/api/v1/studio"


async def _count(model, *where) -> int:
    stmt = select(func.count()).select_from(model.__table__)
    if where:
        stmt = stmt.where(*where)
    async with host.engine.connect() as conn:
        return await conn.scalar(stmt)


# 集成-01：create_project + list_projects —— 项目列表上限 60
async def test_integration_01_project_list_cap(client):
    for i in range(1, 62):
        resp = await client.post(f"{API}/projects", json={"name": f"项目{i}", "description": ""})
        assert resp.status_code == 201

    listing = await client.get(f"{API}/projects")
    assert listing.status_code == 200
    data = listing.json()
    assert len(data) == 60
    assert data[0]["id"] == 61
    assert data[-1]["id"] == 2
    assert await _count(host.studio.Projects) == 61


# 集成-02：append_message + get_project —— 消息读取上限 400
async def test_integration_02_message_read_cap(client):
    pa = (await client.post(f"{API}/projects", json={"name": "甲", "description": ""})).json()
    for i in range(400):
        await client.post(f"{API}/projects/{pa['id']}/messages",
                          json={"role": "user", "kind": "requirement", "content": f"消息{i}"})
    detail_a = (await client.get(f"{API}/projects/{pa['id']}")).json()
    assert len(detail_a["messages"]) == 400

    pb = (await client.post(f"{API}/projects", json={"name": "乙", "description": ""})).json()
    written_ids = []
    for i in range(401):
        r = await client.post(f"{API}/projects/{pb['id']}/messages",
                              json={"role": "user", "kind": "requirement", "content": f"消息{i}"})
        written_ids.append(r.json()["id"])
    detail_b = (await client.get(f"{API}/projects/{pb['id']}")).json()
    returned_ids = [m["id"] for m in detail_b["messages"]]
    assert len(returned_ids) == 400
    assert returned_ids == written_ids[:400]  # 最早 400 条按 id 升序
    assert written_ids[400] not in returned_ids  # 第 401 条不在响应中


# 集成-03：plan —— 计划幂等
async def test_integration_03_plan_idempotent(client):
    project = (await client.post(f"{API}/projects", json={"name": "计划", "description": ""})).json()
    await client.post(f"{API}/projects/{project['id']}/messages",
                      json={"role": "user", "kind": "requirement", "content": "做一个演示页"})

    body = {"requirement": "增加备注", "profile": None}
    r1 = await client.post(f"{API}/projects/{project['id']}/plan", json=body)
    r2 = await client.post(f"{API}/projects/{project['id']}/plan", json=body)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["message"]["id"] == r2.json()["message"]["id"]

    plan_count = await _count(
        host.studio.Studio_messages,
        host.studio.Studio_messages.project_id == project["id"],
        host.studio.Studio_messages.kind == "plan",
    )
    assert plan_count == 1


# 集成-04：artifact —— 构建重放幂等
async def test_integration_04_artifact_replay_idempotent(client):
    project = (await client.post(f"{API}/projects", json={"name": "构建", "description": ""})).json()
    requirement = "增加备注"
    plan_summary = _plan_request_text(studio_output.fixture(requirement)["plan"])
    outline = studio_output.fixture(requirement)["outline"]

    await client.post(f"{API}/projects/{project['id']}/plan", json={"requirement": requirement})
    body = {"requirement": requirement, "plan_summary": plan_summary, "outline": outline}
    r1 = await client.post(f"{API}/projects/{project['id']}/artifact", json=body)
    r2 = await client.post(f"{API}/projects/{project['id']}/artifact", json=body)
    assert r1.status_code == 200 and r2.status_code == 200

    v1, v2 = r1.json()["version"], r2.json()["version"]
    assert v1["version_no"] == v2["version_no"] == 1
    assert v1["id"] == v2["id"]
    assert r2.json()["artifact_html"] == r1.json()["artifact_html"]

    version_count = await _count(
        host.studio.Studio_versions,
        host.studio.Studio_versions.project_id == project["id"],
    )
    build_count = await _count(
        host.studio.Studio_messages,
        host.studio.Studio_messages.project_id == project["id"],
        host.studio.Studio_messages.kind == "build",
    )
    async with host.engine.connect() as conn:
        current = await conn.scalar(
            select(host.studio.Projects.current_version).where(host.studio.Projects.id == project["id"])
        )
    assert version_count == 1
    assert build_count == 1
    assert current == 1


# 集成-05：restore_version —— 恢复幂等（同序号不追加 note）
async def test_integration_05_restore_idempotent(client):
    project = (await client.post(f"{API}/projects", json={"name": "恢复", "description": ""})).json()
    pid = project["id"]

    req1, req2 = "做演示页A", "做演示页B"
    for req in (req1, req2):
        plan_summary = _plan_request_text(studio_output.fixture(req)["plan"])
        outline = studio_output.fixture(req)["outline"]
        await client.post(f"{API}/projects/{pid}/plan", json={"requirement": req})
        await client.post(f"{API}/projects/{pid}/artifact",
                          json={"requirement": req, "plan_summary": plan_summary, "outline": outline})

    # 定位到第一版记录
    async with host.engine.connect() as conn:
        version_id_1 = await conn.scalar(
            select(host.studio.Studio_versions.id)
            .where(host.studio.Studio_versions.project_id == pid)
            .order_by(host.studio.Studio_versions.version_no.asc())
            .limit(1)
        )

    # 第一次恢复到 v1（current_version 由 2 -> 1，追加一条 note）
    await client.post(f"{API}/projects/{pid}/restore", json={"version_id": version_id_1})
    before = await _count(
        host.studio.Studio_messages,
        host.studio.Studio_messages.project_id == pid,
    )

    # 第二次恢复到同一 v1，应直接返回摘要、不追加 note
    resp = await client.post(f"{API}/projects/{pid}/restore", json={"version_id": version_id_1})
    assert resp.status_code == 200
    assert resp.json()["current_version"] == 1

    after = await _count(
        host.studio.Studio_messages,
        host.studio.Studio_messages.project_id == pid,
    )
    assert after == before


# 集成-06：create_project + _commit —— 提交失败回滚
async def test_integration_06_commit_failure_rolls_back(client):
    fault = await client.post("/__test/fault", json={"stage": "commit", "mode": "fail", "remaining": 1})
    assert fault.status_code == 200

    created = await client.post(f"{API}/projects", json={"name": "应失败", "description": ""})
    assert created.status_code == 500
    assert "保存失败" in created.json()["detail"]

    listing = await client.get(f"{API}/projects")
    assert listing.json() == []

    detail = await client.get(f"{API}/projects/1")
    assert detail.status_code == 404

    assert await _count(host.studio.Projects) == 0


# 集成-07：outline —— 阶段二界面结构生成
async def test_integration_07_outline_route(client):
    project = (await client.post(f"{API}/projects", json={"name": "结构", "description": ""})).json()
    resp = await client.post(
        f"{API}/projects/{project['id']}/outline",
        json={"requirement": "做个演示页", "plan_summary": "演示计划一", "profile": None},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "mock-fixed-v1"
    assert data["outline"]["title"] == "演示页面一"
    assert data["outline"]["sections"]


# 集成-08：list_models —— 可切换模型配置
async def test_integration_08_list_models(client):
    resp = await client.get(f"{API}/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_profile"] == "balanced"
    assert [p["key"] for p in data["profiles"]] == ["balanced", "fast", "quality"]


# 集成-09：get_version + get_project current_artifact + restore 404
async def test_integration_09_get_version_and_current_artifact(client):
    project = (await client.post(f"{API}/projects", json={"name": "版本", "description": ""})).json()
    pid = project["id"]
    req = "增加备注"
    plan_summary = _plan_request_text(studio_output.fixture(req)["plan"])
    outline = studio_output.fixture(req)["outline"]
    await client.post(f"{API}/projects/{pid}/plan", json={"requirement": req})
    built = await client.post(
        f"{API}/projects/{pid}/artifact",
        json={"requirement": req, "plan_summary": plan_summary, "outline": outline},
    )
    version_id = built.json()["version"]["id"]

    detail = await client.get(f"{API}/versions/{version_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == version_id
    assert detail.json()["artifact_html"]

    assert (await client.get(f"{API}/versions/999999")).status_code == 404

    # get_project 应回填当前版本的 artifact_html
    project_detail = (await client.get(f"{API}/projects/{pid}")).json()
    assert project_detail["current_artifact"]

    assert (await client.post(f"{API}/projects/{pid}/restore", json={"version_id": 999999})).status_code == 404


# 集成-10：delete_project —— 级联删除消息与版本
async def test_integration_10_delete_project_cascade(client):
    project = (await client.post(f"{API}/projects", json={"name": "删除", "description": ""})).json()
    pid = project["id"]
    await client.post(f"{API}/projects/{pid}/messages",
                      json={"role": "user", "kind": "requirement", "content": "消息"})
    req = "增加备注"
    await client.post(f"{API}/projects/{pid}/plan", json={"requirement": req})
    await client.post(
        f"{API}/projects/{pid}/artifact",
        json={"requirement": req,
              "plan_summary": _plan_request_text(studio_output.fixture(req)["plan"]),
              "outline": studio_output.fixture(req)["outline"]},
    )

    resp = await client.delete(f"{API}/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "id": pid}

    assert (await client.get(f"{API}/projects/{pid}")).status_code == 404
    assert await _count(host.studio.Projects) == 0
    assert await _count(host.studio.Studio_messages) == 0
    assert await _count(host.studio.Studio_versions) == 0


# 集成-11：plan/outline/artifact 故障注入 —— 502 映射
async def test_integration_11_stage_failures_map_502(client):
    project = (await client.post(f"{API}/projects", json={"name": "失败", "description": ""})).json()
    pid = project["id"]

    # 提供者失败 → HTTPException 原样透传 502
    await client.post("/__test/fault", json={"stage": "plan", "mode": "fail", "remaining": 1})
    resp = await client.post(f"{API}/projects/{pid}/plan", json={"requirement": "做个演示页"})
    assert resp.status_code == 502

    await client.post("/__test/fault", json={"stage": "outline", "mode": "fail", "remaining": 1})
    resp = await client.post(f"{API}/projects/{pid}/outline",
                             json={"requirement": "做个演示页", "plan_summary": "x"})
    assert resp.status_code == 502

    await client.post("/__test/fault", json={"stage": "artifact", "mode": "fail", "remaining": 1})
    resp = await client.post(
        f"{API}/projects/{pid}/artifact",
        json={"requirement": "做个演示页", "plan_summary": "x", "outline": {"title": "t", "sections": []}},
    )
    assert resp.status_code == 502

    # 计划结构无效 → 校验失败 502
    await client.post("/__test/fault", json={"stage": "plan", "mode": "invalid", "remaining": 1})
    resp = await client.post(f"{API}/projects/{pid}/plan", json={"requirement": "做个演示页"})
    assert resp.status_code == 502

    # 界面结构无效 → 校验失败 502
    await client.post("/__test/fault", json={"stage": "outline", "mode": "invalid", "remaining": 1})
    resp = await client.post(f"{API}/projects/{pid}/outline",
                             json={"requirement": "做个演示页", "plan_summary": "x"})
    assert resp.status_code == 502

    # 产物 HTML 无效 → 校验失败 502
    await client.post("/__test/fault", json={"stage": "artifact", "mode": "invalid", "remaining": 1})
    resp = await client.post(
        f"{API}/projects/{pid}/artifact",
        json={"requirement": "做个演示页", "plan_summary": "x", "outline": {"title": "t", "sections": []}},
    )
    assert resp.status_code == 502

    # 提供者抛出非 HTTP 异常 → 兜底 502（对账错误信息）
    await client.post("/__test/fault", json={"stage": "plan", "mode": "crash", "remaining": 1})
    resp = await client.post(f"{API}/projects/{pid}/plan", json={"requirement": "做个演示页"})
    assert resp.status_code == 502
    assert "计划生成失败" in resp.json()["detail"]

    await client.post("/__test/fault", json={"stage": "outline", "mode": "crash", "remaining": 1})
    resp = await client.post(f"{API}/projects/{pid}/outline",
                             json={"requirement": "做个演示页", "plan_summary": "x"})
    assert resp.status_code == 502
    assert "界面结构生成失败" in resp.json()["detail"]

    await client.post("/__test/fault", json={"stage": "artifact", "mode": "crash", "remaining": 1})
    resp = await client.post(
        f"{API}/projects/{pid}/artifact",
        json={"requirement": "做个演示页", "plan_summary": "x", "outline": {"title": "t", "sections": []}},
    )
    assert resp.status_code == 502
    assert "产物生成失败" in resp.json()["detail"]