"""构建终端事件服务：落库、读取、序列化与 SSE 帧。

事件类型固定为六种（见 EVENT_TYPES），前端构建终端只依赖这组类型。
一次构建以 (user_id, project_id, build_id) 定位，seq 在构建内递增。
"""
import json
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.build_events import BuildEvent

STAGE_STARTED = "stage_started"
STAGE_FINISHED = "stage_finished"
FILE_CREATED = "file_created"
LOG = "log"
ERROR = "error"
DONE = "done"

#: 固定事件类型清单（顺序即前端展示约定，不随实现变化）。
EVENT_TYPES = (STAGE_STARTED, STAGE_FINISHED, FILE_CREATED, LOG, ERROR, DONE)

#: 终止事件：SSE 在该事件之后主动关闭连接。
TERMINAL_TYPES = (ERROR, DONE)


def _loads(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def serialize_event(row: BuildEvent) -> Dict[str, Any]:
    """把 ORM 行转成对前端稳定的事件结构（data 为对象，不输出正文）。"""
    return {
        "seq": row.seq,
        "type": row.type,
        "stage": row.stage,
        "message": row.message,
        "data": _loads(row.data),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def sse_frame(row: BuildEvent) -> str:
    """SSE 帧：event 字段给原生 EventSource 用，data 带完整 JSON 供 fetch 解析。"""
    payload = json.dumps(serialize_event(row), ensure_ascii=False)
    return f"id: {row.seq}\nevent: {row.type}\ndata: {payload}\n\n"


async def append_event(
    db: AsyncSession,
    *,
    user_id: str,
    project_id: int,
    build_id: str,
    type: str,
    stage: Optional[str] = None,
    message: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> BuildEvent:
    """追加一条事件（不提交事务，由调用方决定提交时机）。"""
    if type not in EVENT_TYPES:
        raise ValueError(f"未知的构建事件类型：{type}")

    latest = await db.scalar(
        select(func.max(BuildEvent.seq)).where(
            BuildEvent.user_id == user_id,
            BuildEvent.project_id == project_id,
            BuildEvent.build_id == build_id,
        )
    )
    row = BuildEvent(
        user_id=user_id,
        project_id=project_id,
        build_id=build_id,
        seq=int(latest or 0) + 1,
        type=type,
        stage=stage,
        message=message,
        data=json.dumps(data or {}, ensure_ascii=False),
    )
    db.add(row)
    await db.flush()
    return row


async def build_exists(
    db: AsyncSession, *, user_id: str, project_id: int, build_id: str
) -> bool:
    """构建是否存在：至少有一条属于该用户与项目的事件。"""
    found = await db.scalar(
        select(func.count(BuildEvent.id)).where(
            BuildEvent.user_id == user_id,
            BuildEvent.project_id == project_id,
            BuildEvent.build_id == build_id,
        )
    )
    return bool(found)


async def list_events(
    db: AsyncSession,
    *,
    user_id: str,
    project_id: int,
    build_id: str,
    after_seq: int = 0,
    limit: int = 500,
) -> List[BuildEvent]:
    result = await db.execute(
        select(BuildEvent)
        .where(
            BuildEvent.user_id == user_id,
            BuildEvent.project_id == project_id,
            BuildEvent.build_id == build_id,
            BuildEvent.seq > after_seq,
        )
        .order_by(BuildEvent.seq.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def latest_build_id(
    db: AsyncSession, *, user_id: str, project_id: int
) -> Optional[str]:
    row = (
        await db.execute(
            select(BuildEvent.build_id)
            .where(
                BuildEvent.user_id == user_id,
                BuildEvent.project_id == project_id,
            )
            .order_by(BuildEvent.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row
