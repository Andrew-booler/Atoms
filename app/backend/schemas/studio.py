"""Studio 接口的 Pydantic 传输对象，只放路由间传递的数据形状，不承载业务逻辑。"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    preview_url: Optional[str] = None


class ExecutionResponse(BaseModel):
    id: int
    version_id: int
    status: str
    preview_url: str
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class RestoreRequest(BaseModel):
    version_id: int