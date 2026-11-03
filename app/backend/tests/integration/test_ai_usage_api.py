"""AI 用量接口集成测试：鉴权、空数据、聚合、时间窗与跨用户隔离。"""
from datetime import datetime, timedelta

from models.ai_usage import AiUsageRecord
from testing import studio_app as host

API = "/api/v1/user/ai-usage"


async def _seed(rows, user_id: str = host.TEST_USER_ID) -> None:
    async with host.sessions() as session:
        for row in rows:
            session.add(
                AiUsageRecord(
                    user_id=user_id,
                    build_id=row.get("build_id"),
                    stage=row.get("stage", "plan"),
                    provider=row.get("provider"),
                    prompt_tokens=row.get("prompt_tokens"),
                    completion_tokens=row.get("completion_tokens"),
                    reasoning_tokens=row.get("reasoning_tokens"),
                    created_at=row.get("created_at", datetime.now().astimezone()),
                )
            )
        await session.commit()


def _today_at(hour: int) -> datetime:
    now = datetime.now().astimezone()
    return now.replace(hour=hour, minute=0, second=0, microsecond=0)


async def test_requires_login(client):
    response = await client.get(API, headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_TOKEN"


async def test_empty_usage_returns_no_data_instead_of_zero(client):
    response = await client.get(API)
    assert response.status_code == 200
    body = response.json()

    assert body["today"]["totals"]["has_data"] is False
    assert body["today"]["totals"]["total_tokens"] is None
    assert body["today"]["providers"] == []
    assert body["last_7_days"]["totals"]["calls"] == 0
    assert body["total"]["totals"]["total_tokens"] is None
    assert body["latest_build"] is None


async def test_aggregates_today_and_provider_breakdown(client):
    await _seed(
        [
            {"provider": "openai", "prompt_tokens": 10, "completion_tokens": 20, "created_at": _today_at(9)},
            {"provider": "aliyun", "prompt_tokens": 5, "completion_tokens": 7, "created_at": _today_at(10)},
            {"provider": "mock", "prompt_tokens": None, "completion_tokens": None, "created_at": _today_at(11)},
        ]
    )

    body = (await client.get(API)).json()
    totals = body["today"]["totals"]
    assert totals["calls"] == 3
    assert totals["prompt_tokens"] == 15
    assert totals["completion_tokens"] == 27
    assert totals["total_tokens"] == 42
    assert totals["reasoning_tokens"] is None
    assert totals["has_data"] is True

    providers = {item["provider"]: item for item in body["today"]["providers"]}
    assert providers["openai"]["total_tokens"] == 30
    assert providers["aliyun"]["total_tokens"] == 12
    assert providers["mock"]["total_tokens"] is None
    assert providers["mock"]["calls"] == 1


async def test_cross_user_isolation(client, other_headers):
    await _seed(
        [{"provider": "openai", "prompt_tokens": 1000, "completion_tokens": 1000}],
        user_id=host.OTHER_USER_ID,
    )

    mine = (await client.get(API)).json()
    assert mine["today"]["totals"]["has_data"] is False
    assert mine["total"]["totals"]["calls"] == 0

    theirs = (await client.get(API, headers=other_headers)).json()
    assert theirs["today"]["totals"]["calls"] == 1
    assert theirs["today"]["totals"]["total_tokens"] == 2000


async def test_window_boundary_excludes_older_than_seven_days(client):
    today_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    await _seed(
        [
            {"provider": "openai", "prompt_tokens": 10, "completion_tokens": 10,
             "created_at": today_start + timedelta(hours=1)},
            {"provider": "aliyun", "prompt_tokens": 100, "completion_tokens": 100,
             "created_at": today_start - timedelta(days=6)},
            {"provider": "aliyun", "prompt_tokens": 1000, "completion_tokens": 1000,
             "created_at": today_start - timedelta(days=8)},
        ]
    )

    body = (await client.get(API)).json()
    assert body["today"]["totals"]["total_tokens"] == 20
    assert body["last_7_days"]["totals"]["total_tokens"] == 220
    assert body["last_7_days"]["totals"]["calls"] == 2
    assert body["total"]["totals"]["total_tokens"] == 2220
    assert body["total"]["totals"]["calls"] == 3


async def test_latest_build_returns_most_recent_build_usage(client):
    now = datetime.now().astimezone()
    await _seed(
        [
            {"provider": "openai", "prompt_tokens": 1, "completion_tokens": 1,
             "build_id": "build-old", "created_at": now - timedelta(hours=2)},
            {"provider": "aliyun", "prompt_tokens": 10, "completion_tokens": 20,
             "build_id": "build-new", "stage": "artifact", "created_at": now},
        ]
    )

    body = (await client.get(API)).json()
    latest = body["latest_build"]
    assert latest["build_id"] == "build-new"
    assert latest["totals"]["total_tokens"] == 30
    assert latest["providers"][0]["provider"] == "aliyun"
