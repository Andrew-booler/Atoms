"""Atoms Cloud 业务接口：全部要求登录，所有查询按 user_id 隔离。"""
import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core import error_codes
from core.database import get_db
from core.exceptions import (
    AppError,
    InternalError,
    NotFoundError,
    ProviderError,
    SandboxUnavailableError,
    ValidationError,
)
from dependencies.auth import get_current_user, get_stream_user
from models.projects import Projects
from models.studio_messages import Studio_messages
from models.studio_versions import Studio_versions
from schemas.auth import UserResponse
from schemas.studio import (
    ArtifactRequest,
    BuildEventOut,
    BuildEventsResponse,
    BuildResponse,
    BuildStartResponse,
    EditArtifactRequest,
    ExecutionResponse,
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
from services import ai_usage
from services import build_events as build_log
from services import studio_output as studio_ai
from services import user_ai_config
from services.aihub import AllProvidersFailedError
from services.execution import ExecutionService
from services.studio_validation import (
    validate_artifact_html,
    validate_outline_payload,
    validate_plan_payload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/studio", tags=["studio"])

#: 构建事件流参数：轮询间隔、心跳间隔与单连接最长存活时间（秒）。
SSE_POLL_SECONDS = 0.4
SSE_HEARTBEAT_SECONDS = 15.0
SSE_MAX_SECONDS = 600.0

#: 三个阶段的中文提示，避免事件文案散落。
_STAGE_TEXT: Dict[str, Tuple[str, str]] = {
    "plan": ("开始生成计划", "计划已生成"),
    "outline": ("开始生成页面结构", "页面结构已生成"),
    "artifact": ("开始生成页面", "页面已生成"),
}



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
        raise InternalError(error_codes.STUDIO_DB_COMMIT_FAILED) from exc


def _provider_details(exc: AllProvidersFailedError) -> Dict[str, Any]:
    """把供应商失败摘要放入 details：保留 provider/model/reason，不含密钥。"""
    details: Dict[str, Any] = {
        "providers": [
            {"provider": failure.provider, "model": failure.model, "reason": failure.reason}
            for failure in exc.failures
        ]
    }
    if any(failure.provider == user_ai_config.USER_PROVIDER_NAME for failure in exc.failures):
        details["fallback_message"] = "自选接入失败，已尝试回退系统默认供应商。"
    return details


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
        # 越权与不存在统一返回 404，避免泄露资源是否存在。
        raise NotFoundError(error_codes.RESOURCE_NOT_FOUND)
    return project


async def _load_version(db: AsyncSession, version_id: int, user_id: str) -> Studio_versions:
    row = (
        await db.execute(
            select(Studio_versions).where(
                Studio_versions.id == version_id,
                Studio_versions.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        # 越权与不存在统一返回 404，避免泄露版本是否存在。
        raise NotFoundError(error_codes.RESOURCE_NOT_FOUND)
    return row


async def _summary(db: AsyncSession, project: Projects) -> ProjectSummary:
    count = await db.scalar(
        select(func.count(Studio_versions.id)).where(
            Studio_versions.project_id == project.id,
            Studio_versions.user_id == project.user_id,
        )
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


# ---------- 构建终端事件 ----------
async def _build_ctx(
    db: AsyncSession, *, project_id: int, user_id: str, build_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    """校验并返回构建上下文；未传 build_id 时返回 None（不记录事件）。

    build_id 属于该用户/项目才有效，否则统一 404，避免泄露构建是否存在。
    """
    if not build_id:
        return None
    if not await build_log.build_exists(
        db, user_id=user_id, project_id=project_id, build_id=build_id
    ):
        raise NotFoundError(error_codes.RESOURCE_NOT_FOUND)
    return {"db": db, "project_id": project_id, "user_id": user_id, "build_id": build_id}


async def _emit_event(
    ctx: Optional[Dict[str, Any]],
    type: str,
    *,
    stage: Optional[str] = None,
    message: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """写一条事件并立即提交，保证正在轮询的 SSE 连接能及时看到。

    事件失败只记日志，绝不阻断主流程（终端是观测能力，不是业务前置条件）。
    """
    if ctx is None:
        return
    try:
        await build_log.append_event(
            ctx["db"],
            user_id=ctx["user_id"],
            project_id=ctx["project_id"],
            build_id=ctx["build_id"],
            type=type,
            stage=stage,
            message=message,
            data=data,
        )
        await ctx["db"].commit()
    except Exception:  # noqa: BLE001 - 观测失败不影响业务
        logger.warning("写入构建事件失败：%s", type, exc_info=True)
        rollback = getattr(ctx["db"], "rollback", None)
        if rollback is not None:
            try:
                await rollback()
            except Exception:  # noqa: BLE001
                pass


class _BuildStage:
    """阶段记录器：进入时发 stage_started，退出时发 stage_finished 或 error。

    ctx 为 None（未传 build_id）时全部为空操作。
    """

    def __init__(self, ctx: Optional[Dict[str, Any]], stage: str, start: str, finish: str):
        self.ctx = ctx
        self.stage = stage
        self.start_message = start
        self.finish_message = finish
        self._started_at = 0.0
        self._usage_token = None

    async def __aenter__(self) -> "_BuildStage":
        self._started_at = time.monotonic()
        self._usage_token = ai_usage.begin_stage()
        await _emit_event(self.ctx, build_log.STAGE_STARTED, stage=self.stage, message=self.start_message)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        usage = ai_usage.finish_stage(self._usage_token) if self._usage_token is not None else None
        fallbacks = ai_usage.fallbacks()
        duration_ms = int((time.monotonic() - self._started_at) * 1000)
        if exc is None:
            await _emit_event(
                self.ctx,
                build_log.STAGE_FINISHED,
                stage=self.stage,
                message=self.finish_message,
                data={"duration_ms": duration_ms, "usage": usage, "fallbacks": fallbacks},
            )
            return False

        if isinstance(exc, AppError):
            code = exc.code
            details = exc.details or {}
        else:  # 未转换的异常：只暴露错误类型，不泄露堆栈
            code = error_codes.INTERNAL_ERROR
            details = {"reason": type(exc).__name__}
        if fallbacks:
            details = {**details, "fallbacks": fallbacks}
        await _emit_event(
            self.ctx,
            build_log.ERROR,
            stage=self.stage,
            message=error_codes.ERROR_MESSAGES.get(code, error_codes.ERROR_MESSAGES[error_codes.INTERNAL_ERROR]),
            data={"code": code, "stage": self.stage, "details": details},
        )
        return False


async def _emit_delivery(
    ctx: Optional[Dict[str, Any]],
    *,
    html: str,
    preview_url: Optional[str],
    preview_details: Dict[str, Any],
    version_no: Optional[int],
) -> None:
    """构建交付事件：写入 index.html → 沙箱摘要 → 完成。"""
    if ctx is None:
        return
    size = len(html.encode("utf-8"))
    await _emit_event(
        ctx,
        build_log.FILE_CREATED,
        message=f"已写入 index.html（{size} 字节）",
        data={"name": "index.html", "bytes": size},
    )
    log_data = {
        "preview_ready": bool(preview_url),
        "stdout": preview_details.get("stdout", ""),
        "stderr": preview_details.get("stderr", ""),
        "files": preview_details.get("files", []),
        "port": preview_details.get("port"),
        "preview_url": preview_url,
        "reason": preview_details.get("reason"),
    }
    await _emit_event(
        ctx,
        build_log.LOG,
        message="沙箱预览已启动" if preview_url else "沙箱预览未启动（产物已保存，可稍后重试）",
        data=log_data,
    )
    await _emit_event(
        ctx,
        build_log.DONE,
        message="构建完成",
        data={"version_no": version_no, "preview_url": preview_url},
    )


def _stream_session_factory(db: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """从请求会话的 bind 派生独立会话，避免复用请求事务/身份映射。"""
    bind = getattr(db, "bind", None)
    if bind is None:  # pragma: no cover - 正常注入的 AsyncSession 一定有 bind
        bind = db.sync_session.bind  # type: ignore[attr-defined]
    return async_sessionmaker(bind, expire_on_commit=False)


async def _require_build(
    db: AsyncSession, *, project_id: int, user_id: str, build_id: str
) -> None:
    if not await build_log.build_exists(
        db, user_id=user_id, project_id=project_id, build_id=build_id
    ):
        raise NotFoundError(error_codes.RESOURCE_NOT_FOUND)



# ---------- Routes ----------
@router.get("/models", response_model=ModelsResponse)
async def list_models(
    current_user: UserResponse = Depends(get_current_user),
) -> ModelsResponse:
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
    await _commit(db)
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
            .where(
                Studio_messages.project_id == project_id,
                Studio_messages.user_id == current_user.id,
            )
            .order_by(Studio_messages.id.asc())
            .limit(400)
        )
    ).scalars().all()

    versions = (
        await db.execute(
            select(Studio_versions)
            .where(
                Studio_versions.project_id == project_id,
                Studio_versions.user_id == current_user.id,
            )
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
    await db.execute(delete(Studio_messages).where(
        Studio_messages.project_id == project.id,
        Studio_messages.user_id == current_user.id,
    ))
    await db.execute(delete(Studio_versions).where(
        Studio_versions.project_id == project.id,
        Studio_versions.user_id == current_user.id,
    ))
    await db.delete(project)
    await _commit(db)
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
    await _commit(db)
    return _message_out(row)


@router.post("/projects/{project_id}/plan", response_model=PlanResponse)
async def plan(
    project_id: int,
    data: PlanRequest,
    build_id: Optional[str] = Query(default=None, max_length=64),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """阶段一：把需求拆成结构化计划，等用户确认后再执行。"""
    project = await _load_project(db, project_id, current_user.id)
    project_name = project.name
    ctx = await _build_ctx(
        db, project_id=project_id, user_id=current_user.id, build_id=build_id
    )
    await _commit(db)

    async with _BuildStage(ctx, "plan", *_STAGE_TEXT["plan"]):
        async with user_ai_config.activate_user_provider(db, current_user.id):
            try:
                raw_plan = await studio_ai.get_provider().plan(
                    data.requirement, project_name=project_name, profile=data.profile
                )
            except AppError:
                raise
            except AllProvidersFailedError as exc:
                logger.error("Studio plan failed: 全部供应商失败")
                raise ProviderError(
                    error_codes.STUDIO_PLAN_FAILED, details=_provider_details(exc)
                ) from exc
            except Exception as exc:  # noqa: BLE001
                logger.error("Studio plan failed: %s", type(exc).__name__)
                raise ProviderError(error_codes.STUDIO_PLAN_FAILED) from exc

        try:
            payload = validate_plan_payload(raw_plan)
        except ValueError as exc:
            raise ProviderError(
                error_codes.STUDIO_PLAN_INVALID, details={"reason": str(exc)}
            ) from exc
        text = _plan_to_text(payload)
        model = studio_ai.resolve_model(data.profile)

        project = await _load_project(db, project_id, current_user.id)
        existing = (await db.execute(select(Studio_messages).where(
            Studio_messages.project_id == project_id,
            Studio_messages.user_id == current_user.id,
            Studio_messages.kind == "plan",
        ).order_by(Studio_messages.id.desc()))).scalars().first()
        latest_user = (await db.execute(select(Studio_messages).where(
            Studio_messages.project_id == project_id,
            Studio_messages.user_id == current_user.id,
            Studio_messages.role == "user",
        ).order_by(Studio_messages.id.desc()))).scalars().first()
        if existing and _parse_meta(existing.meta).get("requirement_message_id") == (latest_user.id if latest_user else None) and _parse_meta(existing.meta).get("requirement") == data.requirement:
            return PlanResponse(plan=PlanPayload(**_parse_meta(existing.meta)["plan"]), message=_message_out(existing), model=model)
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
    build_id: Optional[str] = Query(default=None, max_length=64),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OutlineResponse:
    """阶段二：确认计划后，先产出界面结构与示例数据。"""
    await _load_project(db, project_id, current_user.id)
    ctx = await _build_ctx(
        db, project_id=project_id, user_id=current_user.id, build_id=build_id
    )
    await _commit(db)

    async with _BuildStage(ctx, "outline", *_STAGE_TEXT["outline"]):
        async with user_ai_config.activate_user_provider(db, current_user.id):
            try:
                raw = await studio_ai.get_provider().outline(
                    data.requirement,
                    {"summary": data.plan_summary, "steps": []},
                    profile=data.profile,
                )
            except AppError:
                raise
            except AllProvidersFailedError as exc:
                logger.error("Studio outline failed: 全部供应商失败")
                raise ProviderError(
                    error_codes.STUDIO_OUTLINE_FAILED, details=_provider_details(exc)
                ) from exc
            except Exception as exc:  # noqa: BLE001
                logger.error("Studio outline failed: %s", type(exc).__name__)
                raise ProviderError(error_codes.STUDIO_OUTLINE_FAILED) from exc

        try:
            payload = validate_outline_payload(raw)
        except ValueError as exc:
            raise ProviderError(
                error_codes.STUDIO_OUTLINE_INVALID, details={"reason": str(exc)}
            ) from exc
        return OutlineResponse(outline=payload, model=studio_ai.resolve_model(data.profile))


async def _try_run_preview(
    db: AsyncSession, html: str, version_id: int, user_id: str
) -> Tuple[Optional[str], Dict[str, Any]]:
    """尝试启动沙箱预览；Docker 不可用或失败时返回 (None, 原因)，不抛出。"""
    service = ExecutionService(db)
    try:
        execution = await service.run_html(html, version_id, user_id)
        details = service.last_run_details or {}
        return execution.preview_url, details
    except SandboxUnavailableError as exc:
        logger.warning("沙箱不可用，artifact 已保存但预览未启动：%s", exc.code)
        return None, {"reason": exc.message}
    except Exception as exc:  # noqa: BLE001
        logger.warning("启动沙箱预览失败：%s", exc, exc_info=True)
        return None, {"reason": type(exc).__name__}


@router.post("/projects/{project_id}/artifact", response_model=BuildResponse)
async def artifact(
    project_id: int,
    data: ArtifactRequest,
    build_id: Optional[str] = Query(default=None, max_length=64),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuildResponse:
    """阶段三：产出真正可运行的单文件应用，并保存为新版本。"""
    await _load_project(db, project_id, current_user.id)
    ctx = await _build_ctx(
        db, project_id=project_id, user_id=current_user.id, build_id=build_id
    )
    await _commit(db)

    base_version = None
    if data.base_version_id is not None:
        result = await db.execute(select(Studio_versions).where(
            Studio_versions.id == data.base_version_id,
            Studio_versions.project_id == project_id,
            Studio_versions.user_id == current_user.id,
        ))
        base_version = result.scalar_one_or_none()
        if base_version is None:
            raise NotFoundError(error_codes.RESOURCE_NOT_FOUND)

    preview_url: Optional[str] = None
    preview_details: Dict[str, Any] = {}
    version_no: Optional[int] = None
    response: Optional[BuildResponse] = None
    replay_response: Optional[BuildResponse] = None

    async with _BuildStage(ctx, "artifact", *_STAGE_TEXT["artifact"]):
        async with user_ai_config.activate_user_provider(db, current_user.id):
            try:
                artifact_html = await studio_ai.get_provider().artifact(
                    data.requirement,
                    {"summary": data.plan_summary, "steps": []},
                    data.outline.model_dump(),
                    profile=data.profile,
                    context=base_version.artifact_html if base_version else None,
                    base_version_id=data.base_version_id,
                )
            except AppError:
                raise
            except AllProvidersFailedError as exc:
                logger.error("Studio artifact failed: 全部供应商失败")
                raise ProviderError(
                    error_codes.STUDIO_ARTIFACT_FAILED, details=_provider_details(exc)
                ) from exc
            except Exception as exc:  # noqa: BLE001
                logger.error("Studio artifact failed: %s", type(exc).__name__)
                raise ProviderError(error_codes.STUDIO_ARTIFACT_FAILED) from exc

        try:
            artifact_html = validate_artifact_html(artifact_html)
        except ValueError as exc:
            raise ProviderError(
                error_codes.STUDIO_ARTIFACT_INVALID, details={"reason": str(exc)}
            ) from exc
        project = await _load_project(db, project_id, current_user.id)
        plans = (await db.execute(select(Studio_messages).where(
            Studio_messages.project_id == project_id,
            Studio_messages.user_id == current_user.id,
            Studio_messages.kind == "plan",
        ).order_by(Studio_messages.id.desc()))).scalars().all()
        plan_message = next((row for row in plans if _parse_meta(row.meta).get("requirement") == data.requirement and
            _plan_request_text(_parse_meta(row.meta).get("plan", {})) == data.plan_summary), None)
        if plan_message and _parse_meta(plan_message.meta).get("approved"):
            version_id = _parse_meta(plan_message.meta).get("version_id")
            saved = (await db.execute(select(Studio_versions).where(
                Studio_versions.id == version_id,
                Studio_versions.project_id == project_id,
                Studio_versions.user_id == current_user.id,
            ))).scalar_one()
            builds = (await db.execute(select(Studio_messages).where(
                Studio_messages.project_id == project_id,
                Studio_messages.user_id == current_user.id,
                Studio_messages.kind == "build",
            ))).scalars().all()
            saved_message = next(row for row in builds if _parse_meta(row.meta).get("version_id") == version_id)
            preview_url, preview_details = await _try_run_preview(
                db, saved.artifact_html, saved.id, current_user.id
            )
            version_no = saved.version_no
            replay_response = BuildResponse(
                project=await _summary(db, project),
                version=VersionSummary(id=saved.id, version_no=saved.version_no, label=saved.label, created_at=saved.created_at),
                message=_message_out(saved_message),
                outline_title=data.outline.title,
                artifact_html=saved.artifact_html,
                preview_url=preview_url,
            )
        else:
            latest = await db.scalar(
                select(func.max(Studio_versions.version_no)).where(
                    Studio_versions.project_id == project_id,
                    Studio_versions.user_id == current_user.id,
                )
            )
            next_no = int(latest or 0) + 1
            title = data.outline.title or "原型"
            label = f"v{next_no} · {title}"
            if base_version:
                label += f"（迭代自 v{base_version.version_no}）"
            plan_summary = data.plan_summary or (base_version.plan_summary if base_version else "")

            version = Studio_versions(
                user_id=current_user.id,
                project_id=project_id,
                version_no=next_no,
                label=label,
                plan_summary=plan_summary,
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
                    "base_version_id": data.base_version_id,
                },
            )

            if plan_message:
                meta = _parse_meta(plan_message.meta)
                meta.update(approved=True, version_id=version.id)
                plan_message.meta = json.dumps(meta, ensure_ascii=False)
            project.current_version = next_no
            project.preview_ready = True
            await _commit(db)

            preview_url, preview_details = await _try_run_preview(
                db, artifact_html, version.id, current_user.id
            )
            version_no = version.version_no
            response = BuildResponse(
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
                preview_url=preview_url,
            )

    final = replay_response or response
    assert final is not None
    await _emit_delivery(
        ctx,
        html=final.artifact_html,
        preview_url=preview_url,
        preview_details=preview_details,
        version_no=version_no,
    )
    return final


@router.post("/projects/{project_id}/artifact/edit", response_model=BuildResponse)
async def edit_artifact(
    project_id: int,
    data: EditArtifactRequest,
    build_id: Optional[str] = Query(default=None, max_length=64),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuildResponse:
    """阶段三·编辑：直接修改产物源码，保存为新版本并重跑预览。"""
    project = await _load_project(db, project_id, current_user.id)
    ctx = await _build_ctx(
        db, project_id=project_id, user_id=current_user.id, build_id=build_id
    )
    await _commit(db)

    preview_url: Optional[str] = None
    preview_details: Dict[str, Any] = {}
    version_no: Optional[int] = None
    response: Optional[BuildResponse] = None

    async with _BuildStage(ctx, "artifact", "开始保存编辑", "编辑已保存"):
        try:
            html = validate_artifact_html(data.html)
        except ValueError as exc:
            raise ValidationError(
                error_codes.ARTIFACT_INVALID, details={"reason": str(exc)}
            ) from exc

        base_version = None
        if project.current_version:
            base_version = (await db.execute(select(Studio_versions).where(
                Studio_versions.project_id == project_id,
                Studio_versions.user_id == current_user.id,
                Studio_versions.version_no == project.current_version,
            ))).scalar_one_or_none()

        current_title = "手动编辑"
        if base_version and base_version.label:
            tail = base_version.label.split("·", 1)[-1].strip() if "·" in base_version.label else base_version.label
            tail = tail.split("（")[0].strip()
            current_title = tail or current_title

        latest_no = await db.scalar(
            select(func.max(Studio_versions.version_no)).where(
                Studio_versions.project_id == project_id,
                Studio_versions.user_id == current_user.id,
            )
        )
        next_no = int(latest_no or 0) + 1

        note = data.note.strip()
        label = f"v{next_no} · {current_title}"
        if note:
            label += f" · {note}"

        version = Studio_versions(
            user_id=current_user.id,
            project_id=project_id,
            version_no=next_no,
            label=label,
            plan_summary=base_version.plan_summary if base_version else "",
            artifact_html=html,
        )
        db.add(version)
        await db.flush()

        message = await _append_message(
            db,
            project_id=project_id,
            user_id=current_user.id,
            role="assistant",
            kind="build",
            content=f"已手动编辑产物并保存为 {label}。",
            meta={
                "version_id": version.id,
                "version_no": next_no,
                "title": current_title,
                "model": "manual-edit",
            },
        )

        project.current_version = next_no
        project.preview_ready = True
        await _commit(db)

        preview_url, preview_details = await _try_run_preview(
            db, html, version.id, current_user.id
        )
        version_no = version.version_no
        response = BuildResponse(
            project=await _summary(db, project),
            version=VersionSummary(
                id=version.id,
                version_no=version.version_no,
                label=version.label,
                created_at=version.created_at,
            ),
            message=_message_out(message),
            outline_title=current_title,
            artifact_html=html,
            preview_url=preview_url,
        )

    assert response is not None
    await _emit_delivery(
        ctx,
        html=response.artifact_html,
        preview_url=preview_url,
        preview_details=preview_details,
        version_no=version_no,
    )
    return response


@router.post(
    "/projects/{project_id}/builds",
    response_model=BuildStartResponse,
    status_code=201,
)
async def start_build(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuildStartResponse:
    """为一次完整的 plan→outline→artifact 构建创建终端会话。"""
    await _load_project(db, project_id, current_user.id)
    build_id = uuid.uuid4().hex
    await build_log.append_event(
        db,
        user_id=current_user.id,
        project_id=project_id,
        build_id=build_id,
        type=build_log.LOG,
        message="构建终端已就绪，等待阶段开始。",
        data={},
    )
    await _commit(db)
    return BuildStartResponse(build_id=build_id)


@router.get(
    "/projects/{project_id}/builds/latest",
    response_model=BuildEventsResponse,
)
async def latest_build(
    project_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuildEventsResponse:
    """刷新页面后回看最近一次构建的事件（按 user_id 过滤）。"""
    await _load_project(db, project_id, current_user.id)
    build_id = await build_log.latest_build_id(
        db, user_id=current_user.id, project_id=project_id
    )
    if not build_id:
        return BuildEventsResponse()
    rows = await build_log.list_events(
        db, user_id=current_user.id, project_id=project_id, build_id=build_id
    )
    return BuildEventsResponse(
        build_id=build_id,
        events=[BuildEventOut(**build_log.serialize_event(row)) for row in rows],
    )


@router.get("/projects/{project_id}/builds/{build_id}/stream")
async def stream_build(
    project_id: int,
    build_id: str,
    current_user: UserResponse = Depends(get_stream_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE 事件流：先回放历史事件，再轮询新增事件；遇到 done/error 主动关闭。

    鉴权沿用 Phase 17 的 JWT：优先 Authorization: Bearer，浏览器原生 EventSource
    可用 ?access_token= 查询参数兜底（两者校验逻辑完全一致）。
    """
    await _load_project(db, project_id, current_user.id)
    await _require_build(
        db, project_id=project_id, user_id=current_user.id, build_id=build_id
    )
    user_id = current_user.id
    session_factory = _stream_session_factory(db)

    async def event_stream() -> AsyncIterator[str]:
        last_seq = 0
        started_at = time.monotonic()
        last_beat = started_at
        while True:
            async with session_factory() as session:
                rows = await build_log.list_events(
                    session,
                    user_id=user_id,
                    project_id=project_id,
                    build_id=build_id,
                    after_seq=last_seq,
                )
            for row in rows:
                last_seq = max(last_seq, row.seq)
                yield build_log.sse_frame(row)
                if row.type in build_log.TERMINAL_TYPES:
                    return
            now = time.monotonic()
            if now - started_at >= SSE_MAX_SECONDS:
                return
            if now - last_beat >= SSE_HEARTBEAT_SECONDS:
                last_beat = now
                yield ": keep-alive\n\n"
            await asyncio.sleep(SSE_POLL_SECONDS)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/versions/{version_id}", response_model=VersionDetail)
async def get_version(
    version_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VersionDetail:
    version = await _load_version(db, version_id, current_user.id)
    return VersionDetail(
        id=version.id,
        project_id=version.project_id,
        version_no=version.version_no,
        label=version.label,
        plan_summary=version.plan_summary,
        artifact_html=version.artifact_html,
        created_at=version.created_at,
    )


@router.post("/versions/{version_id}/run", response_model=ExecutionResponse)
async def run_version(
    version_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """对已保存版本重新启动沙箱预览。"""
    version = await _load_version(db, version_id, current_user.id)

    service = ExecutionService(db)
    try:
        execution = await service.run_html(version.artifact_html, version_id, current_user.id)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("启动版本预览失败：%s", type(exc).__name__)
        raise SandboxUnavailableError(
            error_codes.SANDBOX_START_FAILED, details={"reason": type(exc).__name__}
        ) from exc

    return ExecutionResponse(
        id=execution.id,
        version_id=execution.version_id,
        status=execution.status,
        preview_url=execution.preview_url,
        started_at=execution.started_at,
        expires_at=execution.expires_at,
    )


@router.delete("/executions/{execution_id}", response_model=ExecutionResponse)
async def stop_execution(
    execution_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """停止并清理一个沙箱执行。"""
    service = ExecutionService(db)
    execution = await service.stop(execution_id, user_id=current_user.id)
    if execution is None:
        raise NotFoundError(error_codes.RESOURCE_NOT_FOUND)
    return ExecutionResponse(
        id=execution.id,
        version_id=execution.version_id,
        status=execution.status,
        preview_url=execution.preview_url,
        started_at=execution.started_at,
        expires_at=execution.expires_at,
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
        raise NotFoundError(error_codes.RESOURCE_NOT_FOUND)

    if project.current_version == version.version_no:
        return await _summary(db, project)
    project.current_version = version.version_no
    project.preview_ready = True
    await _append_message(
        db,
        project_id=project_id,
        user_id=current_user.id,
        role="system",
        kind="note",
        content=f"已回滚到 v{version.version_no}。",
        meta={"version_id": version.id, "version_no": version.version_no},
    )
    await _commit(db)
    return await _summary(db, project)
