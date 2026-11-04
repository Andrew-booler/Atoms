"""后端-单元：模型档位与供应商绑定的安全边界。

覆盖三件事：
1. 三档档位与真实免费模型的映射（一档一供应商，且模型名不同）；
2. 档位绑定的供应商排在最前，降级家只用自己的模型，模型名不跨家发送；
3. studio_ai 实际调用链使用档位绑定（而不是全局顺序）。

全部使用 mock 客户端，不发起真实网络请求。
"""

import httpx
import pytest
from openai import RateLimitError

from schemas.aihub import ChatMessage, GenTxtRequest
from services import aihub, studio_ai


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


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


def _rate_limit() -> Exception:
    request = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    return RateLimitError("429 rate limited", response=httpx.Response(429, request=request), body=None)


def _configure_three_providers(monkeypatch):
    """三家都配置完整，验证降级链顺序与模型隔离。"""
    monkeypatch.setenv("APP_AI_ALIYUN_API_KEY", "test-aliyun-key")
    monkeypatch.setenv("APP_AI_ALIYUN_BASE_URL", "https://aliyun.example/v1")
    monkeypatch.setenv("APP_AI_ALIYUN_MODEL", "qwen3.8-flash")
    monkeypatch.setenv("APP_AI_ARK_API_KEY", "test-ark-key")
    monkeypatch.setenv("APP_AI_ARK_BASE_URL", "https://ark.example/v1")
    monkeypatch.setenv("APP_AI_ARK_MODEL", "ark-own-model")
    monkeypatch.setenv("APP_AI_ZHIPU_API_KEY", "test-zhipu-key")
    monkeypatch.setenv("APP_AI_ZHIPU_BASE_URL", "https://zhipu.example/v1")
    monkeypatch.setenv("APP_AI_ZHIPU_MODEL", "glm-4.7-flash")
    monkeypatch.setenv("APP_AI_PROVIDER_ORDER", "aliyun,ark,zhipu")


def test_profiles_bind_one_provider_and_distinct_free_models():
    assert studio_ai.DEFAULT_PROFILE == "balanced"
    profiles = studio_ai.MODEL_PROFILES

    assert profiles["fast"]["id"] == "glm-4.7-flash"
    assert profiles["fast"]["provider"] == "zhipu"
    assert profiles["balanced"]["id"] == "qwen3.8-flash"
    assert profiles["balanced"]["provider"] == "aliyun"
    assert profiles["quality"]["id"] == "deepseek-v4-1-flash-economy-261017"
    assert profiles["quality"]["provider"] == "ark"

    # 一档一家，且模型名互不相同：不允许三档共用一个 id。
    assert len({p["provider"] for p in profiles.values()}) == 3
    assert len({p["id"] for p in profiles.values()}) == 3

    models = {item["key"]: item for item in studio_ai.available_models()}
    assert models["fast"]["provider"] == "zhipu"
    assert models["fast"]["model_label"] == "GLM-4.7-Flash"
    assert models["balanced"]["provider_label"] == "阿里百炼"
    assert models["quality"]["provider_label"] == "火山方舟"


def test_resolve_provider_falls_back_to_default_for_unknown_profile():
    assert studio_ai.resolve_provider("fast") == "zhipu"
    assert studio_ai.resolve_provider("unknown") == "aliyun"
    assert studio_ai.resolve_provider(None) == "aliyun"


def test_providers_for_puts_bound_provider_first_and_keeps_own_models(monkeypatch):
    _configure_three_providers(monkeypatch)

    chain = aihub.providers_for("zhipu", "glm-4.7-flash")
    assert [p.name for p in chain] == ["zhipu", "aliyun", "ark"]
    assert chain[0].model == "glm-4.7-flash"
    # 降级家保持自己的模型，档位模型名不会泄漏给别家。
    assert chain[1].model == "qwen3.8-flash"
    assert chain[2].model == "ark-own-model"

    chain = aihub.providers_for("ark", "deepseek-v4-1-flash-economy-261017")
    assert [p.name for p in chain] == ["ark", "aliyun", "zhipu"]
    assert chain[0].model == "deepseek-v4-1-flash-economy-261017"
    assert chain[1].model == "qwen3.8-flash"


def test_providers_for_degrades_to_global_order_when_bound_provider_missing(monkeypatch):
    _configure_three_providers(monkeypatch)
    monkeypatch.delenv("APP_AI_ZHIPU_API_KEY", raising=False)

    chain = aihub.providers_for("zhipu", "glm-4.7-flash")
    assert [p.name for p in chain] == ["aliyun", "ark"]
    assert "glm-4.7-flash" not in {p.model for p in chain}


async def test_fast_profile_429_falls_back_to_aliyun_model_not_deepseek(monkeypatch):
    """快速档（智谱）限流时先降级到百炼自有模型；仍未失败到方舟，不会跑成深度档。"""
    _configure_three_providers(monkeypatch)
    chain = aihub.providers_for("zhipu", "glm-4.7-flash")
    # 单家 429 会先按 AI_MAX_RETRIES 退避重试，耗尽后才降级到下一家。
    clients = {
        "zhipu": _FakeClient([_rate_limit() for _ in range(aihub.AI_MAX_RETRIES + 1)]),
        "aliyun": _FakeClient(["ok"]),
        "ark": _FakeClient(["should-not-be-called"]),
    }
    service = aihub.AIHubService(providers=chain, client_factory=lambda p: clients[p.name])

    response = await service.gentxt(
        GenTxtRequest(
            messages=[ChatMessage(role="user", content="你好")],
            model="glm-4.7-flash",
            max_completion_tokens=32,
        )
    )

    assert response.content == "ok"
    assert response.model == "qwen3.8-flash"
    assert clients["zhipu"].calls[0]["model"] == "glm-4.7-flash"
    assert clients["aliyun"].calls[0]["model"] == "qwen3.8-flash"
    assert clients["ark"].calls == []
    assert response.usage["provider"] == "aliyun"


async def test_studio_gentxt_uses_profile_bound_provider(monkeypatch):
    """studio_ai 实际调用链的首家必须与档位绑定一致，而不是全局顺序。"""
    _configure_three_providers(monkeypatch)
    captured = []

    class _FakeService:
        def __init__(self, providers=None, client_factory=None):
            captured.extend(providers or [])

        async def gentxt(self, request):
            from types import SimpleNamespace

            return SimpleNamespace(content="ok", usage=None)

    monkeypatch.setattr(studio_ai, "AIHubService", _FakeService)

    for profile, provider, model in (
        ("fast", "zhipu", "glm-4.7-flash"),
        ("balanced", "aliyun", "qwen3.8-flash"),
        ("quality", "ark", "deepseek-v4-1-flash-economy-261017"),
    ):
        captured.clear()
        await studio_ai._gentxt("s", "你好", profile=profile, max_completion_tokens=32)
        assert captured[0].name == provider
        assert captured[0].model == model
        # 其余家保持各自模型，档位模型名只出现在首家。
        assert [p.model for p in captured[1:]].count(model) == 0


async def test_studio_gentxt_profile_unknown_uses_default_provider(monkeypatch):
    _configure_three_providers(monkeypatch)
    captured = {}

    class _FakeService:
        def __init__(self, providers=None, client_factory=None):
            captured["providers"] = providers or []

        async def gentxt(self, request):
            from types import SimpleNamespace

            return SimpleNamespace(content="ok", usage=None)

    monkeypatch.setattr(studio_ai, "AIHubService", _FakeService)
    await studio_ai._gentxt("s", "你好", profile="unknown", max_completion_tokens=32)
    assert captured["providers"][0].name == "aliyun"
    assert captured["providers"][0].model == "qwen3.8-flash"
