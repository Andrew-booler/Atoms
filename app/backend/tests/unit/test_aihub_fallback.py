"""AI 调用层多供应商主备降级单测。

全部使用 mock 客户端模拟 HTTP 结果，不依赖真实网络与真实密钥。
覆盖：配置缺失跳过、主备降级顺序、429 触发降级、空响应降级、全部失败、流式建流降级。
"""

import httpx
import pytest
from openai import APITimeoutError, AuthenticationError, InternalServerError, RateLimitError

from schemas.aihub import ChatMessage, GenTxtRequest
from services import aihub


# ==================== 测试替身 ====================


class _Message:
    def __init__(self, content):
        self.content = content


class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)
        self.delta = _Delta(content)


class _Usage:
    prompt_tokens = 1
    completion_tokens = 1
    total_tokens = 2


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]
        self.usage = _Usage()


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        item = self._chunks.pop(0)
        if isinstance(item, BaseException):
            raise item
        return _Response(item)


class _FakeClient:
    """模拟 AsyncOpenAI 的 chat.completions.create。

    behaviors 依次消费：Exception 表示抛出该异常；str 表示返回该文本；
    list 表示流式返回的 chunk 列表。
    """

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
        if kwargs.get("stream"):
            return _FakeStream(item)
        return _Response(item)


def _request() -> GenTxtRequest:
    return GenTxtRequest(
        messages=[ChatMessage(role="user", content="你好")],
        model="qwen3.8-flash",
        max_tokens=32,
    )


def _provider(name: str, model: str) -> aihub.ProviderConfig:
    return aihub.ProviderConfig(
        name=name,
        base_url=f"https://{name}.example/v1",
        api_key="test-key",
        model=model,
        max_tokens=16,
        max_concurrency=1,
        timeout=5.0,
    )


def _service(providers, clients) -> aihub.AIHubService:
    return aihub.AIHubService(providers=providers, client_factory=lambda p: clients[p.name])


def _http_request() -> httpx.Request:
    return httpx.Request("POST", "https://example.invalid/v1/chat/completions")


def _rate_limit() -> Exception:
    return RateLimitError("429 rate limited", response=httpx.Response(429, request=_http_request()), body=None)


def _server_error() -> Exception:
    return InternalServerError("500 server error", response=httpx.Response(500, request=_http_request()), body=None)


def _timeout() -> Exception:
    return APITimeoutError(_http_request())


def _auth_error() -> Exception:
    return AuthenticationError("401 unauthorized", response=httpx.Response(401, request=_http_request()), body=None)


# ==================== fixtures ====================

_ENV_KEYS = [
    "APP_AI_PROVIDER_ORDER",
    "APP_AI_ALIYUN_BASE_URL",
    "APP_AI_ALIYUN_API_KEY",
    "APP_AI_ALIYUN_MODEL",
    "APP_AI_ARK_BASE_URL",
    "APP_AI_ARK_API_KEY",
    "APP_AI_ARK_MODEL",
    "APP_AI_ZHIPU_BASE_URL",
    "APP_AI_ZHIPU_API_KEY",
    "APP_AI_ZHIPU_MODEL",
    "APP_AI_BASE_URL",
    "APP_AI_KEY",
]


@pytest.fixture(autouse=True)
def _fast_retry(monkeypatch):
    """避免单测真实等待：退避归零，每家最多重试 1 次。"""
    monkeypatch.setattr(aihub, "_backoff_seconds", lambda attempt: 0.0)
    monkeypatch.setattr(aihub, "AI_MAX_RETRIES", 1)


@pytest.fixture
def clean_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


# ==================== 配置构建 ====================


def test_build_providers_skips_unconfigured(clean_env):
    """仅配置智谱时，只构建出一家（其他家因缺 key 被跳过）。"""
    clean_env.setenv("APP_AI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
    clean_env.setenv("APP_AI_KEY", "zhipu-key")

    providers = aihub._build_providers()

    assert [p.name for p in providers] == ["zhipu"]
    assert providers[0].model == "glm-4.7-flash"
    assert aihub.has_configured_provider() is True


def test_build_providers_aliyun_defaults(clean_env):
    """阿里百炼缺省使用北京域名与 qwen3.8-flash 模型。"""
    clean_env.setenv("APP_AI_ALIYUN_API_KEY", "aliyun-key")

    providers = aihub._build_providers()

    assert [p.name for p in providers] == ["aliyun"]
    assert providers[0].base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert providers[0].model == "qwen3.8-flash"


def test_build_providers_ark_requires_model(clean_env):
    """火山方舟必须显式配置 model（推理接入点 ID 或模型 ID），否则跳过。"""
    clean_env.setenv("APP_AI_ARK_API_KEY", "ark-key")
    assert aihub.configured_provider_names() == []

    clean_env.setenv("APP_AI_ARK_MODEL", "ep-test-endpoint")
    providers = aihub._build_providers()
    assert [p.name for p in providers] == ["ark"]
    assert providers[0].base_url == "https://ark.cn-beijing.volces.com/api/v3"
    assert providers[0].model == "ep-test-endpoint"


def test_build_providers_empty_when_nothing_configured(clean_env):
    assert aihub._build_providers() == []
    assert aihub.has_configured_provider() is False


# ==================== 降级行为 ====================


async def test_429_degrades_to_next_provider():
    """主选 429（含一次重试）后降级到备选并成功。"""
    aliyun = _FakeClient([_rate_limit(), _rate_limit()])
    ark = _FakeClient(["来自方舟的回复"])
    providers = [_provider("aliyun", "qwen3.8-flash"), _provider("ark", "doubao-endpoint")]
    service = _service(providers, {"aliyun": aliyun, "ark": ark})

    result = await service.gentxt(_request())

    assert result.content == "来自方舟的回复"
    assert result.model == "doubao-endpoint"
    # 每家独立计数：aliyun 重试 1 次共 2 次调用，ark 首次即成功。
    assert len(aliyun.calls) == 2
    assert len(ark.calls) == 1


async def test_empty_response_degrades_to_next_provider():
    """空响应视为失败并降级，不重试同一家。"""
    aliyun = _FakeClient([""])
    ark = _FakeClient(["ok from ark"])
    providers = [_provider("aliyun", "qwen3.8-flash"), _provider("ark", "doubao-endpoint")]
    service = _service(providers, {"aliyun": aliyun, "ark": ark})

    result = await service.gentxt(_request())

    assert result.content == "ok from ark"
    assert len(aliyun.calls) == 1
    assert len(ark.calls) == 1


async def test_auth_error_degrades_without_retry():
    """无效密钥（401）属非瞬时错误：不重试，立即降级到下一家。"""
    aliyun = _FakeClient([_auth_error()])
    ark = _FakeClient(["ok from ark"])
    providers = [_provider("aliyun", "qwen3.8-flash"), _provider("ark", "doubao-endpoint")]
    service = _service(providers, {"aliyun": aliyun, "ark": ark})

    result = await service.gentxt(_request())

    assert result.content == "ok from ark"
    assert len(aliyun.calls) == 1
    assert len(ark.calls) == 1


async def test_all_providers_fail_raises_with_details():
    """三家全部失败时抛 AllProvidersFailedError，携带逐家原因。"""
    aliyun = _FakeClient([_rate_limit(), _rate_limit()])
    ark = _FakeClient([_server_error(), _server_error()])
    zhipu = _FakeClient([_timeout(), _timeout()])
    providers = [
        _provider("aliyun", "qwen3.8-flash"),
        _provider("ark", "doubao-endpoint"),
        _provider("zhipu", "glm-4.7-flash"),
    ]
    service = _service(providers, {"aliyun": aliyun, "ark": ark, "zhipu": zhipu})

    with pytest.raises(aihub.AllProvidersFailedError) as exc_info:
        await service.gentxt(_request())

    failures = exc_info.value.failures
    assert [f.provider for f in failures] == ["aliyun", "ark", "zhipu"]
    assert "RateLimitError" in failures[0].reason
    assert "InternalServerError" in failures[1].reason
    assert "APITimeoutError" in failures[2].reason


async def test_stream_degrades_when_build_fails():
    """流式建流阶段 429 降级到下一家，并正常产出内容。"""
    aliyun = _FakeClient([_rate_limit(), _rate_limit()])
    ark = _FakeClient([["好", "的"]])
    providers = [_provider("aliyun", "qwen3.8-flash"), _provider("ark", "doubao-endpoint")]
    service = _service(providers, {"aliyun": aliyun, "ark": ark})

    chunks = [chunk async for chunk in service.gentxt_stream(_request())]

    assert chunks == ["好", "的"]
