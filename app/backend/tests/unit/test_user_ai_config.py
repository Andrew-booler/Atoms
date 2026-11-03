"""用户自选 AI 配置单测：加密、掩码、优先级、降级与连通性探测。

全部使用替身，不连数据库、不发真实网络请求。
"""
import logging

import httpx
import pytest
from openai import AuthenticationError

from core.user_ai_crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from schemas.aihub import ChatMessage, GenTxtRequest
from services import ai_usage, aihub, user_ai_config

# ==================== 替身 ====================


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)
        self.delta = _Message(content)


class _Usage:
    prompt_tokens = 1
    completion_tokens = 1
    total_tokens = 2


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]
        self.usage = _Usage()


class _FakeClient:
    def __init__(self, behaviors):
        self.behaviors = list(behaviors)
        self.calls = []
        self.chat = self
        self.completions = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.behaviors.pop(0)
        if isinstance(item, BaseException):
            raise item
        return _Response(item)


def _request() -> GenTxtRequest:
    return GenTxtRequest(
        messages=[ChatMessage(role="user", content="你好")],
        model="user-model",
        max_completion_tokens=32,
    )


def _provider(name: str, model: str) -> aihub.ProviderConfig:
    return aihub.ProviderConfig(
        name=name,
        base_url=f"https://{name}.example/v1",
        api_key="user-secret-key",
        model=model,
        max_concurrency=1,
        timeout=5.0,
    )


def _http_request() -> httpx.Request:
    return httpx.Request("POST", "https://example.invalid/v1/chat/completions")


def _auth_error() -> Exception:
    return AuthenticationError("401 unauthorized", response=httpx.Response(401, request=_http_request()), body=None)


@pytest.fixture(autouse=True)
def _fast_retry(monkeypatch):
    monkeypatch.setattr(aihub, "_backoff_seconds", lambda attempt: 0.0)
    monkeypatch.setattr(aihub, "AI_MAX_RETRIES", 0)


# ==================== 加解密与掩码 ====================


def test_encrypt_decrypt_roundtrip_and_never_plaintext():
    plain = "sk-1234567890abcd"
    encrypted = encrypt_api_key(plain)
    assert plain not in encrypted
    assert decrypt_api_key(encrypted) == plain


def test_mask_api_key_keeps_prefix_and_suffix():
    assert mask_api_key("sk-1234567890abcd") == "sk-****abcd"
    assert mask_api_key("short") == "****"
    assert mask_api_key(None) is None


def test_encrypt_and_mask_do_not_log_key(caplog):
    plain = "sk-very-secret-1234"
    with caplog.at_level(logging.DEBUG):
        encrypt_api_key(plain)
        mask_api_key(plain)
    assert plain not in caplog.text


# ==================== 优先级与降级 ====================


def test_user_provider_is_first_in_chain(monkeypatch):
    monkeypatch.setenv("APP_AI_ALIYUN_API_KEY", "system-key")
    user = _provider(user_ai_config.USER_PROVIDER_NAME, "user-model")
    token = aihub.set_user_provider(user)
    try:
        providers = aihub._build_providers()
    finally:
        aihub.reset_user_provider(token)

    assert [p.name for p in providers] == ["user_custom", "aliyun"]
    assert aihub.has_configured_provider() is True


async def test_user_provider_failure_falls_back_and_marks_system():
    user_client = _FakeClient([_auth_error()])
    system_client = _FakeClient(["系统默认回复"])
    providers = [
        _provider(user_ai_config.USER_PROVIDER_NAME, "user-model"),
        _provider("aliyun", "qwen3.8-flash"),
    ]
    service = aihub.AIHubService(
        providers=providers,
        client_factory=lambda p: user_client if p.name == "user_custom" else system_client,
    )

    token = ai_usage.begin_stage()
    try:
        result = await service.gentxt(_request())
    finally:
        ai_usage.finish_stage(token)

    assert result.content == "系统默认回复"
    falls = ai_usage.fallbacks()
    assert falls[0]["from"] == "user_custom"
    assert falls[0]["to"] == "aliyun"
    assert falls[0]["fallback_to_system"] is True
    assert "已回退系统默认" in falls[0]["message"]
    assert "user-secret-key" not in str(falls)


# ==================== 连通性探测（mock transport，零真实请求） ====================


async def _probe_with(handler):
    user_ai_config.HTTP_TRANSPORT = httpx.MockTransport(handler)
    try:
        return await user_ai_config.probe_config(
            "https://api.example/v1", "sk-secret-abcd", "demo-model"
        )
    finally:
        user_ai_config.HTTP_TRANSPORT = None


async def test_probe_success_and_headers():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"data": []})

    ok, message, status, _ = await _probe_with(handler)
    assert ok is True
    assert status == 200
    assert seen["url"] == "https://api.example/v1/models"
    assert seen["auth"] == "Bearer sk-secret-abcd"
    assert "sk-secret-abcd" not in message


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (401, "401"),
        (403, "403"),
        (404, "404"),
    ],
)
async def test_probe_maps_http_errors(code, expected):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(code, json={"error": "nope"})

    ok, message, status, _ = await _probe_with(handler)
    assert ok is False
    assert status == code
    assert expected in message


async def test_probe_timeout_message():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    ok, message, status, _ = await _probe_with(handler)
    assert ok is False
    assert status is None
    assert "超时" in message
