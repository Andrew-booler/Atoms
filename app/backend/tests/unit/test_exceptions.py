"""后端-单元-09：统一异常契约（AppError 分级、码表、脱敏、全局处理器）。"""

import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from core import error_codes
from core.exception_handlers import register_exception_handlers
from core.exceptions import (
    AppError,
    AuthError,
    ConflictError,
    InternalError,
    NotFoundError,
    PayloadTooLargeError,
    ProviderError,
    RateLimitError,
    SandboxUnavailableError,
    ValidationError,
    sanitize_details,
)
from core.log_redaction import SensitiveDataFilter, redact_sensitive_text
from services.aihub import AllProvidersFailedError, ProviderFailure


def _client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    class Payload(BaseModel):
        name: str

    @app.get("/app-error")
    def app_error():
        raise NotFoundError(error_codes.STUDIO_PROJECT_NOT_FOUND)

    @app.get("/validation")
    def validation():
        raise ValidationError(error_codes.ARTIFACT_INVALID, details={"reason": "缺少 body"})

    @app.post("/validate-body")
    def validate_body(payload: Payload):
        return {"name": payload.name}

    @app.get("/http-error")
    def http_error():
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/boom")
    def boom():
        raise RuntimeError("db url postgresql://user:pass@host/db")

    @app.get("/all-failed")
    def all_failed():
        raise AllProvidersFailedError(
            [ProviderFailure("bailian", "qwen3.8-flash", "api_key=sk-secretsecret123 failed")]
        )

    return TestClient(app, raise_server_exceptions=False)


def test_every_code_has_chinese_message():
    assert error_codes.ERROR_MESSAGES
    for code, message in error_codes.ERROR_MESSAGES.items():
        assert code.count("_") >= 1, f"错误码必须是 DOMAIN_REASON: {code}"
        assert message.strip()
        assert any("\u4e00" <= char <= "\u9fff" for char in message), f"{code} 缺少中文文案"


@pytest.mark.parametrize(
    ("exception", "status"),
    [
        (ValidationError, 422),
        (NotFoundError, 404),
        (ConflictError, 409),
        (RateLimitError, 429),
        (PayloadTooLargeError, 413),
        (AuthError, 401),
        (ProviderError, 502),
        (SandboxUnavailableError, 503),
        (InternalError, 500),
    ],
)
def test_error_subclasses_default_status(exception, status):
    assert exception().http_status == status
    assert isinstance(exception(), AppError)


def test_sanitize_details_masks_secrets_and_truncates():
    payload = {
        "api_key": "sk-real",
        "authorization": "Bearer abc",
        "reason": "failed with api_key=sk-secretsecret123",
        "long": "x" * 600,
        "nested": {"password": "p", "items": [{"token": "t"}]},
    }
    cleaned = sanitize_details(payload)
    assert cleaned["api_key"] == "[已隐藏]"
    assert cleaned["authorization"] == "[已隐藏]"
    assert "sk-secretsecret123" not in cleaned["reason"]
    assert cleaned["long"].endswith("...(已截断)")
    assert cleaned["nested"]["password"] == "[已隐藏]"
    assert cleaned["nested"]["items"][0]["token"] == "[已隐藏]"


def test_redact_sensitive_text_covers_db_url_and_bearer():
    raw = "postgresql://postgres:pass@127.0.0.1:5432/db Authorization: Bearer abc123456789"
    cleaned = redact_sensitive_text(raw)
    assert "postgres:pass@" not in cleaned
    assert "abc123456789" not in cleaned


def test_sensitive_data_filter_redacts_message_and_traceback():
    try:
        raise RuntimeError("postgresql://postgres:pass@127.0.0.1/db Authorization: Bearer token123456789")
    except RuntimeError:
        import sys
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="api_key=sk-abcdefghijklmnop",
        args=(),
        exc_info=exc_info,
    )
    SensitiveDataFilter().filter(record)
    assert "sk-abcdefghijklmnop" not in record.getMessage()
    assert "postgres:pass@" not in record.exc_text
    assert "token123456789" not in record.exc_text


def test_app_error_contract():
    response = _client().get("/app-error")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "STUDIO_PROJECT_NOT_FOUND"
    assert body["message"] == "项目不存在或已被删除。"
    assert "details" not in body


def test_validation_error_contract_with_details():
    response = _client().get("/validation")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "ARTIFACT_INVALID"
    assert body["details"] == {"reason": "缺少 body"}


def test_request_validation_error_maps_to_chinese_message():
    response = _client().post("/validate-body", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INTERNAL_VALIDATION_FAILED"
    assert body["message"] == "请求参数有误，请检查后重试。"
    assert body["details"]["fields"] == ["body.name"]


def test_http_exception_maps_to_contract_without_raw_detail():
    response = _client().get("/http-error")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "INTERNAL_RESOURCE_MISSING"
    assert body["message"] == "请求的资源不存在。"
    assert "Not Found" not in response.text


def test_unhandled_exception_is_generic_500_without_internals():
    response = _client().get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert body["message"] == "服务器内部错误，请稍后重试。"
    assert "postgresql" not in response.text
    assert "Traceback" not in response.text


def test_all_providers_failed_keeps_provider_details_but_redacts_keys():
    response = _client().get("/all-failed")
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "INTERNAL_PROVIDER_FAILED"
    providers = body["details"]["providers"]
    assert providers[0]["provider"] == "bailian"
    assert providers[0]["model"] == "qwen3.8-flash"
    assert "sk-secretsecret123" not in response.text
