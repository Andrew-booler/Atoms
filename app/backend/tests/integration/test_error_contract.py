"""后端-错误契约-01～04：对外错误响应结构统一且不泄露内部细节。"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from core.error_codes import ARTIFACT_INVALID
from core.exception_handlers import register_exception_handlers
from core.exceptions import NotFoundError, ValidationError


@pytest.fixture()
def client():
    app = FastAPI()
    register_exception_handlers(app)

    class Payload(BaseModel):
        name: str

    @app.get("/missing")
    def missing():
        raise NotFoundError("STUDIO_PROJECT_NOT_FOUND")

    @app.post("/invalid")
    def invalid():
        raise ValidationError(ARTIFACT_INVALID, details={"reason": "缺少 body"})

    @app.post("/validate")
    def validate(payload: Payload):
        return {"name": payload.name}

    @app.get("/legacy")
    def legacy():
        raise HTTPException(status_code=404, detail="Internal path: /srv/app/data")

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret=sk-live-abcdefghijklmnop")

    return TestClient(app, raise_server_exceptions=False)


def test_not_found_returns_code_and_chinese_message(client):
    response = client.get("/missing")
    assert response.status_code == 404
    assert response.json() == {"code": "STUDIO_PROJECT_NOT_FOUND", "message": "项目不存在或已被删除。"}


def test_validation_error_is_readable_chinese(client):
    response = client.post("/validate", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INTERNAL_VALIDATION_FAILED"
    assert body["message"] == "请求参数有误，请检查后重试。"
    assert body["details"]["fields"] == ["body.name"]


def test_legacy_http_exception_hides_raw_detail(client):
    response = client.get("/legacy")
    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"
    assert "Internal path" not in response.text


def test_unhandled_exception_returns_generic_500_without_secret(client):
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json() == {"code": "INTERNAL_ERROR", "message": "服务器内部错误，请稍后重试。"}
    assert "sk-live" not in response.text
    assert "Traceback" not in response.text
