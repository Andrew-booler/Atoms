"""确定性输出边界。

默认返回示例驱动的预置输出（见 studio_examples），真实提供者须显式注入
或通过环境变量启用。三个阶段（plan/outline/artifact）保持同一响应形状，
前端与存储层无需感知底层是 mock 还是真实模型。
"""

from copy import deepcopy
from typing import Protocol

from services.studio_examples import fixture as example_fixture

# 向后兼容的公开出口：历史调用方（测试、宿主注入）依赖 studio_output.fixture。
fixture = example_fixture

DEFAULT_PROFILE = "balanced"


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
    """真实模型输出：通过注入的 adapter 委托三阶段生成。"""

    def __init__(self, adapter: OutputProvider):
        self.adapter = adapter

    async def plan(self, requirement: str, **kwargs) -> dict:
        return await self.adapter.plan(requirement, **kwargs)

    async def outline(self, requirement: str, plan: dict, **kwargs) -> dict:
        return await self.adapter.outline(requirement, plan, **kwargs)

    async def artifact(self, requirement: str, plan: dict, outline: dict, **kwargs) -> str:
        return await self.adapter.artifact(requirement, plan, outline, **kwargs)


_provider: OutputProvider = MockOutputProvider()


def get_provider() -> OutputProvider:
    return _provider


def resolve_model(profile=None) -> str:
    return "mock-fixed-v1"


def available_models() -> list:
    return [{"key": key, "model": "mock-fixed-v1", "label": label, "hint": "预置输出，不调用真实AI"}
            for key, label in [("balanced", "默认模拟"), ("fast", "快速模拟"), ("quality", "完整模拟")]]