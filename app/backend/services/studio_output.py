"""确定性输出边界：默认只返回预置数据，真实提供者须显式注入。"""
from copy import deepcopy
from typing import Protocol

DEFAULT_PROFILE = "balanced"


def fixed_html(second: bool = False) -> str:
    label = "模拟第二版" if second else "模拟第一版"
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{label}</title>
<style>body{{font-family:system-ui;margin:32px;color:#1a1a18;background:#fafaf8}}button{{padding:12px;background:#c2410c;color:white;border:0;border-radius:8px}}:focus-visible{{outline:3px solid #15803d}}</style></head>
<body><h1>{label}</h1><p>固定预览文档，不调用真实模型。</p><button id="counter">演示计数：0</button>
<script>let count=0;document.getElementById('counter').onclick=function(){{this.textContent='演示计数：'+(++count)}};</script></body></html>'''


def fixture(requirement: str) -> dict:
    second = "增加备注" in requirement
    return {
        "plan": {"summary": "演示计划二" if second else "演示计划一", "stack": ["HTML"],
                 "steps": [{"title": "显示备注" if second else "显示演示", "detail": "使用第二套预置页面" if second else "使用预置页面"}],
                 "files": [{"path": "index.html", "purpose": "固定预览"}]},
        "outline": {"title": "演示页面二" if second else "演示页面一", "sections": [{"name": "备注区" if second else "演示区", "blocks": ["计数"]}],
                    "interactions": ["演示计数"], "seed_data": ["0"]},
        "html": fixed_html(second),
    }


class OutputProvider(Protocol):
    async def plan(self, requirement: str, **kwargs) -> dict: ...
    async def outline(self, requirement: str, plan: dict, **kwargs) -> dict: ...
    async def artifact(self, requirement: str, plan: dict, outline: dict, **kwargs) -> str: ...


class MockOutputProvider:
    async def plan(self, requirement: str, **kwargs) -> dict:
        return deepcopy(fixture(requirement)["plan"])

    async def outline(self, requirement: str, plan: dict, **kwargs) -> dict:
        return deepcopy(fixture(requirement)["outline"])

    async def artifact(self, requirement: str, plan: dict, outline: dict, **kwargs) -> str:
        return fixture(requirement)["html"]


class RealOutputProvider:
    """仅保留注入契约，默认不创建、不调用真实模型。"""
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
