"""Phase 17：/studio/* 登录要求与跨用户数据隔离。

跨用户统一返回 404 RESOURCE_NOT_FOUND，与“资源不存在”不可区分，避免泄露存在性。
"""
from datetime import datetime, timedelta, timezone

import pytest

from models.execution import Execution
from models.studio_versions import Studio_versions
from testing import studio_app as host

STUDIO = "/api/v1/studio"


async def _create_project(client, name: str, headers=None) -> int:
    response = await client.post(f"{STUDIO}/projects", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _missing(response, status: int = 404) -> None:
    assert response.status_code == status, response.text
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.parametrize(
    "path",
    [f"{STUDIO}/models", f"{STUDIO}/projects"],
)
async def test_studio_requires_login(client, path):
    response = await client.get(path, headers={"Authorization": ""})

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


async def test_list_projects_only_returns_own_rows(client, other_headers):
    mine = await _create_project(client, "我的项目")
    other = await _create_project(client, "别人的项目", other_headers)

    # 默认客户端属于 TEST_USER，other_headers 属于 OTHER_USER。
    other_list = await client.get(f"{STUDIO}/projects", headers=other_headers)

    assert other_list.status_code == 200
    assert [row["id"] for row in other_list.json()] == [other]
    assert mine not in [row["id"] for row in other_list.json()]


async def test_other_user_cannot_read_or_delete_project(client, other_headers):
    project_id = await _create_project(client, "私有项目")

    _missing(await client.get(f"{STUDIO}/projects/{project_id}", headers=other_headers))
    _missing(await client.delete(f"{STUDIO}/projects/{project_id}", headers=other_headers))

    # 原用户仍可正常访问，说明上面的 404 不是误删。
    assert (await client.get(f"{STUDIO}/projects/{project_id}")).status_code == 200


async def test_other_user_cannot_append_message_or_plan(client, other_headers):
    project_id = await _create_project(client, "私有项目")

    message = await client.post(
        f"{STUDIO}/projects/{project_id}/messages",
        json={"role": "user", "kind": "requirement", "content": "越权写入"},
        headers=other_headers,
    )
    _missing(message)

    plan = await client.post(
        f"{STUDIO}/projects/{project_id}/plan",
        json={"requirement": "越权规划"},
        headers=other_headers,
    )
    _missing(plan)


async def test_other_user_cannot_read_or_run_version(client, other_headers):
    project_id = await _create_project(client, "私有项目")
    async with host.sessions() as session:
        version = Studio_versions(
            user_id=host.TEST_USER_ID,
            project_id=project_id,
            version_no=1,
            label="v1",
            plan_summary="初始版本",
            artifact_html="<html><body>private</body></html>",
        )
        session.add(version)
        await session.commit()
        version_id = version.id

    _missing(await client.get(f"{STUDIO}/versions/{version_id}", headers=other_headers))
    _missing(await client.post(f"{STUDIO}/versions/{version_id}/run", headers=other_headers))

    restore = await client.post(
        f"{STUDIO}/projects/{project_id}/restore",
        json={"version_id": version_id},
        headers=other_headers,
    )
    _missing(restore)

    assert (await client.get(f"{STUDIO}/versions/{version_id}")).status_code == 200


async def test_other_user_cannot_stop_execution(client, other_headers):
    async with host.sessions() as session:
        execution = Execution(
            user_id=host.TEST_USER_ID,
            version_id=1,
            port=1,
            status="running",
            preview_url="http://127.0.0.1:1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(execution)
        await session.commit()
        execution_id = execution.id

    _missing(await client.delete(f"{STUDIO}/executions/{execution_id}", headers=other_headers))


async def test_forged_user_id_in_body_is_ignored(client, other_headers):
    response = await client.post(
        f"{STUDIO}/projects",
        json={"name": "伪造归属", "user_id": host.OTHER_USER_ID},
    )
    assert response.status_code == 201
    created = response.json()

    other_list = await client.get(f"{STUDIO}/projects", headers=other_headers)
    assert created["id"] not in [row["id"] for row in other_list.json()]
    assert created["id"] in [row["id"] for row in (await client.get(f"{STUDIO}/projects")).json()]
