"""仅测试宿主，不进入生产自动发现路由；复用Atoms Cloud业务实现。"""
import asyncio
import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from routers import studio
from services import studio_output
from core.database import get_db
from models.execution import Execution

SCHEMA = os.environ.get("STUDIO_TEST_SCHEMA", "studio_test_t1")
if not re.fullmatch(r"studio_test_[a-z0-9_]+", SCHEMA):
    raise RuntimeError("测试命名空间必须以studio_test_开头")
engine = create_async_engine(
    os.environ["DATABASE_URL"],
    execution_options={"schema_translate_map": {None: SCHEMA}},
    poolclass=NullPool,
)
state = {"stage": "", "mode": "", "remaining": 0}


class TestSession(AsyncSession):
    async def commit(self):
        if state["stage"] in ("commit", "write_commit") and state["remaining"] > 0 and (state["stage"] == "commit" or self.new or self.dirty or self.deleted):
            state["remaining"] -= 1
            raise RuntimeError("受控提交失败")
        await super().commit()


sessions = async_sessionmaker(engine, class_=TestSession, expire_on_commit=False)


async def database():
    async with sessions() as session:
        yield session


class ControlledProvider(studio_output.MockOutputProvider):
    async def control(self, stage):
        if state["stage"] == stage and state["remaining"] > 0:
            state["remaining"] -= 1
            if state["mode"] == "delay":
                await asyncio.sleep(1)
            elif state["mode"] == "invalid":
                return True
            elif state["mode"] == "crash":
                raise RuntimeError("受控非HTTP异常")
            else:
                raise HTTPException(502, "受控模拟阶段失败")
        return False

    async def plan(self, requirement, **kwargs):
        if await self.control("plan"): return {"summary": "缺字段"}
        return await super().plan(requirement, **kwargs)

    async def outline(self, requirement, plan, **kwargs):
        if await self.control("outline"): return {"title": "缺字段"}
        return await super().outline(requirement, plan, **kwargs)

    async def artifact(self, requirement, plan, outline, **kwargs):
        if await self.control("artifact"): return ""
        return await super().artifact(requirement, plan, outline, **kwargs)


TABLES = [studio.Projects.__table__, studio.Studio_messages.__table__, studio.Studio_versions.__table__, Execution.__table__]


@asynccontextmanager
async def lifespan(app):
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
        await connection.run_sync(lambda sync: studio.Projects.metadata.create_all(sync, tables=TABLES))
    studio_output._provider = ControlledProvider()
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.dependency_overrides[get_db] = database
app.include_router(studio.router)


@app.post('/__test/reset')
async def reset():
    state.update(stage="", mode="", remaining=0)
    async with engine.begin() as connection:
        await connection.execute(text(f'TRUNCATE "{SCHEMA}".studio_messages, "{SCHEMA}".studio_versions, "{SCHEMA}".projects, "{SCHEMA}".executions RESTART IDENTITY'))
    return {"schema": SCHEMA, "reset": True}


@app.post('/__test/fault')
async def fault(data: dict):
    state.update(stage=data.get('stage', ''), mode=data.get('mode', 'fail'), remaining=int(data.get('remaining', 1)))
    return state


@app.middleware('http')
async def read_fault(request, call_next):
    if '/versions/' in request.url.path and state['stage'] == 'read' and state['remaining'] > 0:
        state['remaining'] -= 1
        from starlette.responses import JSONResponse
        return JSONResponse({'detail': '受控读取失败'}, status_code=503)
    return await call_next(request)
