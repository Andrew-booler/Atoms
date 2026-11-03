"""确定性输出边界。

默认返回示例驱动的预置输出（见 studio_examples），真实提供者须显式注入
或通过环境变量启用（任一 AI 供应商配置完整即可，见 services.aihub._build_providers）。
三个阶段（plan/outline/artifact）保持同一响应形状，前端与存储层无需感知底层是
mock 还是真实模型。

真实模式下，若用户输入命中示例文本（见 studio_examples.match_example），
则短路返回对应示范网页，不调用真实模型，保证首体验稳定。
"""

from copy import deepcopy
from typing import Optional, Protocol

from services import aihub, studio_ai
from services.studio_examples import fixture as example_fixture
from services.studio_examples import match_example

# 向后兼容的公开出口：历史调用方（测试、宿主注入）依赖 studio_output.fixture。
fixture = example_fixture

DEFAULT_PROFILE = "balanced"


def _ai_enabled() -> bool:
    """真实 AI 是否已配置：任一供应商（aliyun/ark/zhipu）配置完整即启用。"""
    return aihub.has_configured_provider()


class OutputProvider(Protocol):  # pragma: no cover - 类型协议，无运行时逻辑
    async def plan(self, requirement: str, **kwargs) -> dict: ...  # pragma: no cover
    async def outline(self, requirement: str, plan: dict, **kwargs) -> dict: ...  # pragma: no cover
    async def artifact(self, requirement: str, plan: dict, outline: dict, **kwargs) -> str: ...  # pragma: no cover


class MockOutputProvider:
    """示例驱动的确定性输出，命中示例返回对应示范网页，否则返回通用演示页。"""

    async def plan(self, requirement: str, **kwargs) -> dict:
        return deepcopy(example_fixture(requirement)["plan"])

    async def outline(self, requirement: str, plan: dict, **kwargs) -> dict:
        return deepcopy(example_fixture(requirement)["outline"])

    async def artifact(self, requirement: str, plan: dict, outline: dict, **kwargs) -> str:
        return example_fixture(requirement)["html"]


class RealOutputProvider:
    """真实模型输出：命中示例即短路返回示范网页，否则委托 studio_ai 生成。"""

    async def plan(self, requirement: str, **kwargs) -> dict:
        example = match_example(requirement)
        if example is not None:
            return deepcopy(example["plan"])
        return await studio_ai.generate_plan(
            requirement,
            project_name=kwargs.get("project_name", ""),
            context=kwargs.get("context", ""),
            profile=kwargs.get("profile"),
        )

    async def outline(self, requirement: str, plan: dict, **kwargs) -> dict:
        example = match_example(requirement)
        if example is not None:
            return deepcopy(example["outline"])
        return await studio_ai.generate_outline(requirement, plan, profile=kwargs.get("profile"))

    async def artifact(self, requirement: str, plan: dict, outline: dict, **kwargs) -> str:
        example = match_example(requirement)
        if example is not None:
            return example["html"]
        return await studio_ai.generate_artifact(
            requirement,
            plan,
            outline,
            profile=kwargs.get("profile"),
            context=kwargs.get("context"),
        )


_provider: Optional[OutputProvider] = None


def get_provider() -> OutputProvider:
    """返回当前 Provider：注入优先；否则按当前请求是否配置了 AI 动态选择。

    用户自选接入通过 ContextVar 生效，因此不能把 Mock 实例永久缓存，
    否则配置后同一进程内仍会继续用模拟输出。
    """
    if _provider is not None:
        return _provider
    return RealOutputProvider() if _ai_enabled() else MockOutputProvider()


def resolve_model(profile=None) -> str:
    if _ai_enabled():
        return studio_ai.resolve_model(profile)
    return "mock-fixed-v1"


def available_models() -> list:
    if _ai_enabled():
        return studio_ai.available_models()
    return [{"key": key, "model": "mock-fixed-v1", "label": label, "hint": "预置输出，不调用真实AI"}
            for key, label in [("balanced", "默认模拟"), ("fast", "快速模拟"), ("quality", "完整模拟")]]