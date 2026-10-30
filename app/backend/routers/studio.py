"""Studio 业务接口：项目、对话消息、版本产物、AI 生成阶段。

所有读写都按当前登录用户隔离；AI 调用统一走 services/studio_ai.py 的适配层。
生成被拆成「计划 → 界面结构 → 可运行产物」三个独立接口，每个接口只做一次模型调用，
前端据此呈现真实的分阶段进度，而不是假进度条。

会话边界：慢速 AI 调用前先 commit 收尾 DB 阶段，写入在调用完成后的新 DB 阶段完成。
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from models.projects import Projects
from models.studio_messages import Studio_messages
from models.studio_versions import Studio_versions
from schemas.auth import UserResponse
from services import studio_ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/studio", tags=["studio"])


# ---------- Schemas ----------
class ModelOption(BaseModel):
    key: str
    model: str
    label: str
    hint: str


class ModelsResponse(BaseModel):
    profiles: List[ModelOption]
    default_profile: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""


class ProjectSummary(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    current_version: Optional[int] = None
    preview_ready: Optional[bool] = None
    version_count: int = 0
    updated_at: Optional[datetime] = None


class MessageOut(BaseModel):
    id: int
    role: str
    kind: Optional[str] = None
    content: str
    meta: Dict[str, Any] = {}
    created_at: Optional[datetime] = None


class MessageCreate(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    kind: str = "requirement"
    content: str
    meta: Dict[str, Any] = {}


class VersionSummary(BaseModel):
    id: int
    version_no: int
    label: Optional[str] = None
    created_at: Optional[datetime] = None


class VersionDetail(VersionSummary):
    project_id: int
    plan_summary: Optional[str] = None
    artifact_html: str


class ProjectDetail(BaseModel):
    project: ProjectSummary
    messages: List[MessageOut]
    versions: List[VersionSummary]
    current_artifact: Optional[str] = None


class PlanRequest(BaseModel):
    requirement: str = Field(min_length=1)
    profile: Optional[str] = None


class PlanPayload(BaseModel):
    summary: str
    stack: List[str] = []
    steps: List[Dict[str, str]] = []
    files: List[Dict[str, str]] = []


class PlanResponse(BaseModel):
    plan: PlanPayload
    message: MessageOut
    model: str


class OutlineRequest(BaseModel):
    requirement: str = Field(min_length=1)
    plan_summary: str = ""
    profile: Optional[str] = None


class OutlinePayload(BaseModel):
    title: str
    sections: List[Dict[str, Any]] = []
    interactions: List[str] = []
    seed_data: List[str] = []


class OutlineResponse(BaseModel):
    outline: OutlinePayload
    model: str


class ArtifactRequest(BaseModel):
    requirement: str = Field(min_length=1)
    plan_summary: str = ""
    outline: OutlinePayload
    profile: Optional[str] = None


class BuildResponse(BaseModel):
    project: ProjectSummary
    version: VersionSummary
    message: MessageOut
    outline_title: str
    artifact_html: str


class RestoreRequest(BaseModel):
    version_id: int


# ---------- Helpers ----------
def _parse_meta(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _message_out(row: Studio_messages) -> MessageOut:
    return MessageOut(
        id=row.id,
        role=row.role,
        kind=row.kind,
        content=row.content,
        meta=_parse_meta(row.meta),
        created_at=row.created_at,
    )


def _plan_to_text(plan: PlanPayload) -> str:
    lines = [plan.summary, ""]
    for index, step in enumerate(plan.steps, start=1):
        detail = step.get("detail") or ""
        lines.append(f"{index}. {step.get('title', '')}" + (f" — {detail}" if detail else ""))
    if plan.files:
        lines.append("")
        lines.append("产出文件：" + "、".join(item.get("path", "") for item in plan.files))
    return "\n".join(lines).strip()


async def _load_project(db: AsyncSession, project_id: int, user_id: str) -> Projects:
    result = await db.execute(
        select(Projects).where(Projects.id == project_id, Projects.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    return project


async def _summary(db: AsyncSession, project: Projects) -> ProjectSummary:
    count = await db.scalar(
        select(func.count(Studio_versions.id)).where(Studio_versions.project_id == project.id)
    )
    return ProjectSummary(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        current_version=project.current_version,
        preview_ready=bool(project.preview_ready),
        version_count=int(count or 0),
        updated_at=project.updated_at,
    )


async def _append_message(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: str,
    role: str,
    kind: str,
    content: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Studio_messages:
    row = Studio_messages(
        user_id=user_id,
        project_id=project_id,
        role=role,
        kind=kind,
        content=content,
        meta=json.dumps(meta or {}, ensure_ascii=False),
    )
    db.add(row)
    await db.flush()
    return row


# ---------- Routes ----------
@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """可切换的 AI 配置；前端只拿到 profile 与模型 id，不接触任何密钥。"""
    return ModelsResponse(
        profiles=[ModelOption(**item) for item in studio_ai.available_models()],
        default_profile=studio_ai.DEFAULT_PROFILE,
    )


@router.get("/projects", response_model=List[ProjectSummary])
async def list_projects(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ProjectSummary]:
    result = await db.execute(
        select(Projects)
        .where(Projects.user_id == current_user.id)
        .order_by(Projects.updated_at.desc(), Projects.id.desc())
        .limit(60)
    )
    return [await _summary(db, project) for project in result.scalars().all()]


@router.post("/projects", response_model=ProjectSummary, status_code=201)
async def create_project(
    data: ProjectCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectSummary:
    project = Projects(
        user_id=current_user.id,
        name=data.name.strip(),
        description=data.description.strip(),
        status="active",
        current_version=0,
        preview_ready=False,
    )
    db.add(project)
    await db.commit()
    return await _summary(db, project)


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectDetail:
    project = await _load_project(db, project_id, current_user.id)

    messages = (
        await db.execute(
            select(Studio_messages)
            .where(Studio_messages.project_id == project_id)
            .order_by(Studio_messages.id.asc())
            .limit(400)
        )
    ).scalars().all()

    versions = (
        await db.execute(
            select(Studio_versions)
            .where(Studio_versions.project_id == project_id)
            .order_by(Studio_versions.version_no.desc())
        )
    ).scalars().all()

    current_artifact: Optional[str] = None
    if versions and project.current_version:
        for row in versions:
            if row.version_no == project.current_version:
                current_artifact = row.artifact_html
                break

    return ProjectDetail(
        project=await _summary(db, project),
        messages=[_message_out(row) for row in messages],
        versions=[
            VersionSummary(
                id=row.id,
                version_no=row.version_no,
                label=row.label,
                created_at=row.created_at,
            )
            for row in versions
        ],
        current_artifact=current_artifact,
    )


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    project = await _load_project(db, project_id, current_user.id)
    await db.execute(delete(Studio_messages).where(Studio_messages.project_id == project.id))
    await db.execute(delete(Studio_versions).where(Studio_versions.project_id == project.id))
    await db.delete(project)
    await db.commit()
    return {"deleted": True, "id": project_id}


@router.post("/projects/{project_id}/messages", response_model=MessageOut, status_code=201)
async def append_message(
    project_id: int,
    data: MessageCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    project = await _load_project(db, project_id, current_user.id)
    row = await _append_message(
        db,
        project_id=project_id,
        user_id=current_user.id,
        role=data.role,
        kind=data.kind,
        content=data.content,
        meta=data.meta,
    )
    project.updated_at = datetime.now()
    await db.commit()
    return _message_out(row)


@router.post("/projects/{project_id}/plan", response_model=PlanResponse)
async def plan(
    project_id: int,
    data: PlanRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """阶段一：把需求拆成结构化计划，等用户确认后再执行。"""
    project = await _load_project(db, project_id, current_user.id)
    project_name = project.name
    await db.commit()

    try:
        raw_plan = await studio_ai.generate_plan(
            data.requirement, project_name=project_name, profile=data.profile
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Studio plan failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"计划生成失败，请重试：{exc}") from exc

    payload = PlanPayload(**raw_plan)
    text = _plan_to_text(payload)
    model = studio_ai.resolve_model(data.profile)

    project = await _load_project(db, project_id, current_user.id)
    message = await _append_message(
        db,
        project_id=project_id,
        user_id=current_user.id,
        role="assistant",
        kind="plan",
        content=text,
        meta={
            "plan": payload.model_dump(),
            "model": model,
            "requirement": data.requirement[:2000],
            "approved": False,
        },
    )
    if not (project.description or "").strip():
        project.description = data.requirement[:2000]
    project.updated_at = datetime.now()
    await db.commit()

    return PlanResponse(plan=payload, message=_message_out(message), model=model)


@router.post("/projects/{project_id}/outline", response_model=OutlineResponse)
async def outline(
    project_id: int,
    data: OutlineRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OutlineResponse:
    """阶段二：确认计划后，先产出界面结构与示例数据。"""
    await _load_project(db, project_id, current_user.id)
    await db.commit()

    try:
        raw = await studio_ai.generate_outline(
            data.requirement,
            {"summary": data.plan_summary, "steps": []},
            profile=data.profile,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Studio outline failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"界面结构生成失败，请重试：{exc}") from exc

    return OutlineResponse(
        outline=OutlinePayload(**raw), model=studio_ai.resolve_model(data.profile)
    )


@router.post("/projects/{project_id}/artifact", response_model=BuildResponse)
async def artifact(
    project_id: int,
    data: ArtifactRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuildResponse:
    """阶段三：产出真正可运行的单文件应用，并保存为新版本。"""
    await _load_project(db, project_id, current_user.id)
    await db.commit()

    try:
        artifact_html = await studio_ai.generate_artifact(
            data.requirement,
            {"summary": data.plan_summary, "steps": []},
            data.outline.model_dump(),
            profile=data.profile,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Studio artifact failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"产物生成失败，请重试：{exc}") from exc

    project = await _load_project(db, project_id, current_user.id)
    latest = await db.scalar(
        select(func.max(Studio_versions.version_no)).where(
            Studio_versions.project_id == project_id
        )
    )
    next_no = int(latest or 0) + 1
    title = data.outline.title or "原型"

    version = Studio_versions(
        user_id=current_user.id,
        project_id=project_id,
        version_no=next_no,
        label=f"v{next_no} · {title}",
        plan_summary=data.plan_summary[:4000],
        artifact_html=artifact_html,
    )
    db.add(version)
    await db.flush()

    message = await _append_message(
        db,
        project_id=project_id,
        user_id=current_user.id,
        role="assistant",
        kind="build",
        content=f"已生成「{title}」的可运行版本 v{next_no}。",
        meta={
            "version_id": version.id,
            "version_no": next_no,
            "title": title,
            "sections": [section.get("name") for section in data.outline.sections],
            "interactions": data.outline.interactions,
            "model": studio_ai.resolve_model(data.profile),
        },
    )

    project.current_version = next_no
    project.preview_ready = True
    project.updated_at = datetime.now()
    await db.commit()

    return BuildResponse(
        project=await _summary(db, project),
        version=VersionSummary(
            id=version.id,
            version_no=version.version_no,
            label=version.label,
            created_at=version.created_at,
        ),
        message=_message_out(message),
        outline_title=title,
        artifact_html=artifact_html,
    )


@router.get("/versions/{version_id}", response_model=VersionDetail)
async def get_version(
    version_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VersionDetail:
    result = await db.execute(
        select(Studio_versions).where(
            Studio_versions.id == version_id, Studio_versions.user_id == current_user.id
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="版本不存在或无权访问")
    return VersionDetail(
        id=version.id,
        project_id=version.project_id,
        version_no=version.version_no,
        label=version.label,
        plan_summary=version.plan_summary,
        artifact_html=version.artifact_html,
        created_at=version.created_at,
    )


@router.post("/projects/{project_id}/restore", response_model=ProjectSummary)
async def restore_version(
    project_id: int,
    data: RestoreRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectSummary:
    project = await _load_project(db, project_id, current_user.id)
    result = await db.execute(
        select(Studio_versions).where(
            Studio_versions.id == data.version_id,
            Studio_versions.project_id == project_id,
            Studio_versions.user_id == current_user.id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="版本不存在或无权访问")

    project.current_version = version.version_no
    project.preview_ready = True
    project.updated_at = datetime.now()
    await _append_message(
        db,
        project_id=project_id,
        user_id=current_user.id,
        role="system",
        kind="note",
        content=f"已回滚到 v{version.version_no}。",
        meta={"version_id": version.id, "version_no": version.version_no},
    )
    await db.commit()
    return await _summary(db, project)
