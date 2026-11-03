"""用户自选 AI 接入集成测试：仅本人可见、PUT 生效、DELETE 回退、测试接口 mock transport。"""
import httpx
import pytest

from services import user_ai_config

API = "/api/v1/user/ai-config"
PAYLOAD = {
    "base_url": "https://api.example/v1",
    "api_key": "sk-1234567890abcd",
    "model": "demo-model",
}


async def test_get_unconfigured_returns_false(client):
    response = await client.get(API)
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["api_key_masked"] is None


async def test_put_then_get_returns_masked_key_only(client):
    response = await client.put(API, json=PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["base_url"] == "https://api.example/v1"
    assert body["model"] == "demo-model"
    assert body["api_key_masked"] == "sk-****abcd"
    assert body["message"] == "已启用自选接入。"
    assert PAYLOAD["api_key"] not in response.text

    again = await client.get(API)
    assert again.json()["api_key_masked"] == "sk-****abcd"
    assert PAYLOAD["api_key"] not in again.text


async def test_cross_user_cannot_see_or_delete(client, other_headers):
    await client.put(API, json=PAYLOAD)

    other_get = await client.get(API, headers=other_headers)
    assert other_get.status_code == 200
    assert other_get.json()["configured"] is False

    other_delete = await client.delete(API, headers=other_headers)
    assert other_delete.status_code == 404
    assert other_delete.json()["code"] == "RESOURCE_NOT_FOUND"

    # 本人配置不受影响。
    mine = await client.get(API)
    assert mine.json()["configured"] is True


async def test_delete_clears_and_falls_back(client):
    await client.put(API, json=PAYLOAD)

    response = await client.delete(API)
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    after = await client.get(API)
    assert after.json()["configured"] is False

    missing = await client.delete(API)
    assert missing.status_code == 404


@pytest.fixture
def mock_transport(monkeypatch):
    def install(handler):
        monkeypatch.setattr(user_ai_config, "HTTP_TRANSPORT", httpx.MockTransport(handler))

    return install


async def test_test_endpoint_success_with_mock_transport(client, mock_transport):
    mock_transport(lambda request: httpx.Response(200, json={"data": []}))
    await client.put(API, json=PAYLOAD)

    response = await client.post(f"{API}/test")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "连接成功" in body["message"]
    assert PAYLOAD["api_key"] not in response.text


async def test_test_endpoint_401_has_locating_message(client, mock_transport):
    mock_transport(lambda request: httpx.Response(401, json={"error": "unauthorized"}))
    await client.put(API, json=PAYLOAD)

    response = await client.post(f"{API}/test")
    body = response.json()
    assert body["ok"] is False
    assert body["status_code"] == 401
    assert "401" in body["message"]
    assert PAYLOAD["api_key"] not in response.text


async def test_test_endpoint_requires_config(client):
    response = await client.post(f"{API}/test")
    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"
