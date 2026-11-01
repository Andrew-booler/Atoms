"""Atoms Cloud共享业务接口：真实持久化，默认预置输出，无产品登录门禁。"""
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.projects import Projects
from models.studio_messages import Studio_messages
from models.studio_versions import Studio_versions
from schemas.studio import (
    ArtifactRequest,
    BuildResponse,
    MessageCreate,
    MessageOut,
    ModelOption,
    ModelsResponse,
    OutlinePayload,
    OutlineRequest,
    OutlineResponse,
    PlanPayload,
    PlanRequest,
    PlanResponse,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    RestoreRequest,
    VersionDetail,
    VersionSummary,
)
from services import studio_output as studio_ai
from services.studio_validation import (
    validate_artifact_html,
    validate_outline_payload,
    validate_plan_payload,
)

SHARED_CONTEXT = "studio-shared"

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/studio", tags=["studio"])


# ---------- Helpers ----------
def _plan_request_text(plan: dict) -> str:
    return "\n".join([plan.get("summary", ""), "", *[
        f"{i}. {step.get('title', '')} — {step.get('detail', '')}"
        for i, step in enumerate(plan.get("steps", []), 1)
    ]])


async def _commit(db: AsyncSession):
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("Studio持久化失败")
        raise HTTPException(status_code=500, detail="保存失败，未提交本次变更，请重试") from exc

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
        select(Projects).where(Projects.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
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
    db: AsyncSession = Depends(get_db),
) -> List[ProjectSummary]:
    result = await db.execute(
        select(Projects)
                .order_by(Projects.updated_at.desc(), Projects.id.desc())
        .limit(60)
    )
    return [await _summary(db, project) for project in result.scalars().all()]


@router.post("/projects", response_model=ProjectSummary, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectSummary:
    project = Projects(
        user_id=SHARED_CONTEXT,
        name=data.name.strip(),
        description=data.description.strip(),
        status="active",
        current_version=0,
        preview_ready=False,
    )
    db.add(project)
    await _commit(db)
    return await _summary(db, project)


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProjectDetail:
    project = await _load_project(db, project_id, SHARED_CONTEXT)

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
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    project = await _load_project(db, project_id, SHARED_CONTEXT)
    await db.execute(delete(Studio_messages).where(Studio_messages.project_id == project.id))
    await db.execute(delete(Studio_versions).where(Studio_versions.project_id == project.id))
    await db.delete(project)
    await _commit(db)
    return {"deleted": True, "id": project_id}


@router.post("/projects/{project_id}/messages", response_model=MessageOut, status_code=201)
async def append_message(
    project_id: int,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    project = await _load_project(db, project_id, SHARED_CONTEXT)
    row = await _append_message(
        db,
        project_id=project_id,
        user_id=SHARED_CONTEXT,
        role=data.role,
        kind=data.kind,
        content=data.content,
        meta=data.meta,
    )
    await _commit(db)
    return _message_out(row)


@router.post("/projects/{project_id}/plan", response_model=PlanResponse)
async def plan(
    project_id: int,
    data: PlanRequest,
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """阶段一：把需求拆成结构化计划，等用户确认后再执行。"""
    project = await _load_project(db, project_id, SHARED_CONTEXT)
    project_name = project.name
    await _commit(db)

    try:
        raw_plan = await studio_ai.get_provider().plan(
            data.requirement, project_name=project_name, profile=data.profile
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Studio plan failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"计划生成失败，请重试：{exc}") from exc

    try:
        payload = validate_plan_payload(raw_plan)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    text = _plan_to_text(payload)
    model = studio_ai.resolve_model(data.profile)

    project = await _load_project(db, project_id, SHARED_CONTEXT)
    existing = (await db.execute(select(Studio_messages).where(
        Studio_messages.project_id == project_id, Studio_messages.kind == "plan"
    ).order_by(Studio_messages.id.desc()))).scalars().first()
    latest_user = (await db.execute(select(Studio_messages).where(
        Studio_messages.project_id == project_id, Studio_messages.role == "user"
    ).order_by(Studio_messages.id.desc()))).scalars().first()
    if existing and _parse_meta(existing.meta).get("requirement_message_id") == (latest_user.id if latest_user else None) and _parse_meta(existing.meta).get("requirement") == data.requirement:
        return PlanResponse(plan=PlanPayload(**_parse_meta(existing.meta)["plan"]), message=_message_out(existing), model=model)
    message = await _append_message(
        db,
        project_id=project_id,
        user_id=SHARED_CONTEXT,
        role="assistant",
        kind="plan",
        content=text,
        meta={
            "plan": payload.model_dump(),
            "model": model,
            "requirement": data.requirement,
            "approved": False,
            "requirement_message_id": latest_user.id if latest_user else None,
        },
    )
    if not (project.description or "").strip():
        project.description = data.requirement
    await _commit(db)

    return PlanResponse(plan=payload, message=_message_out(message), model=model)


@router.post("/projects/{project_id}/outline", response_model=OutlineResponse)
async def outline(
    project_id: int,
    data: OutlineRequest,
    db: AsyncSession = Depends(get_db),
) -> OutlineResponse:
    """阶段二：确认计划后，先产出界面结构与示例数据。"""
    await _load_project(db, project_id, SHARED_CONTEXT)
    await _commit(db)

    try:
        raw = await studio_ai.get_provider().outline(
            data.requirement,
            {"summary": data.plan_summary, "steps": []},
            profile=data.profile,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Studio outline failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"界面结构生成失败，请重试：{exc}") from exc

    try:
        payload = validate_outline_payload(raw)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return OutlineResponse(outline=payload, model=studio_ai.resolve_model(data.profile))


@router.post("/projects/{project_id}/artifact", response_model=BuildResponse)
async def artifact(
    project_id: int,
    data: ArtifactRequest,
    db: AsyncSession = Depends(get_db),
) -> BuildResponse:
    """阶段三：产出真正可运行的单文件应用，并保存为新版本。"""
    await _load_project(db, project_id, SHARED_CONTEXT)
    await _commit(db)

    try:
        artifact_html = await studio_ai.get_provider().artifact(
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

    try:
        artifact_html = validate_artifact_html(artifact_html)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    project = await _load_project(db, project_id, SHARED_CONTEXT)
    plans = (await db.execute(select(Studio_messages).where(
        Studio_messages.project_id == project_id, Studio_messages.kind == "plan"
    ).order_by(Studio_messages.id.desc()))).scalars().all()
    plan_message = next((row for row in plans if _parse_meta(row.meta).get("requirement") == data.requirement and
        _plan_request_text(_parse_meta(row.meta).get("plan", {})) == data.plan_summary), None)
    if plan_message and _parse_meta(plan_message.meta).get("approved"):
        version_id = _parse_meta(plan_message.meta).get("version_id")
        saved = (await db.execute(select(Studio_versions).where(Studio_versions.id == version_id))).scalar_one()
        builds = (await db.execute(select(Studio_messages).where(Studio_messages.project_id == project_id, Studio_messages.kind == "build"))).scalars().all()
        saved_message = next(row for row in builds if _parse_meta(row.meta).get("version_id") == version_id)
        return BuildResponse(project=await _summary(db, project), version=VersionSummary(id=saved.id,version_no=saved.version_no,label=saved.label,created_at=saved.created_at),message=_message_out(saved_message),outline_title=data.outline.title,artifact_html=saved.artifact_html)
    latest = await db.scalar(
        select(func.max(Studio_versions.version_no)).where(
            Studio_versions.project_id == project_id
        )
    )
    next_no = int(latest or 0) + 1
    title = data.outline.title or "原型"

    version = Studio_versions(
        user_id=SHARED_CONTEXT,
        project_id=project_id,
        version_no=next_no,
        label=f"v{next_no} · {title}",
        plan_summary=data.plan_summary,
        artifact_html=artifact_html,
    )
    db.add(version)
    await db.flush()

    message = await _append_message(
        db,
        project_id=project_id,
        user_id=SHARED_CONTEXT,
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

    if plan_message:
        meta = _parse_meta(plan_message.meta)
        meta.update(approved=True, version_id=version.id)
        plan_message.meta = json.dumps(meta, ensure_ascii=False)
    project.current_version = next_no
    project.preview_ready = True
    await _commit(db)

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
    db: AsyncSession = Depends(get_db),
) -> VersionDetail:
    result = await db.execute(
        select(Studio_versions).where(Studio_versions.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="版本不存在")
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
    db: AsyncSession = Depends(get_db),
) -> ProjectSummary:
    project = await _load_project(db, project_id, SHARED_CONTEXT)
    result = await db.execute(
        select(Studio_versions).where(
            Studio_versions.id == data.version_id,
            Studio_versions.project_id == project_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="版本不存在")

    if project.current_version == version.version_no:
        return await _summary(db, project)
    project.current_version = version.version_no
    project.preview_ready = True
    await _append_message(
        db,
        project_id=project_id,
        user_id=SHARED_CONTEXT,
        role="system",
        kind="note",
        content=f"已回滚到 v{version.version_no}。",
        meta={"version_id": version.id, "version_no": version.version_no},
    )
    await _commit(db)
    return await _summary(db, project)
