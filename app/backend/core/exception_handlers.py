"""全局异常处理器注册。

统一契约：{"code": DOMAIN_REASON, "message": 中文文案, "details": {...}?}
生产入口（main.py）与接口测试宿主都通过 register_exception_handlers 注册，
避免测试与线上契约漂移。
"""

import logging
import traceback

from core.error_codes import (
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    INTERNAL_ERROR,
    INTERNAL_PROVIDER_FAILED,
    INTERNAL_VALIDATION_FAILED,
)
from core.exceptions import AppError, ProviderError
from core.log_redaction import redact_sensitive_text
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from services.aihub import AllProvidersFailedError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _error_response(code: str, message: str, http_status: int, details: dict | None = None) -> JSONResponse:
    content: dict = {"code": code, "message": message}
    if details:
        content["details"] = details
    return JSONResponse(status_code=http_status, content=content)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("%s %s -> %s (%s)", request.method, request.url.path, exc.code, exc.http_status)
    return _error_response(exc.code, exc.message, exc.http_status, exc.details)


async def all_providers_failed_handler(request: Request, exc: AllProvidersFailedError) -> JSONResponse:
    details = {
        "providers": [
            {"provider": failure.provider, "model": failure.model, "reason": failure.reason}
            for failure in exc.failures
        ]
    }
    error = ProviderError(INTERNAL_PROVIDER_FAILED, details=details)
    return await app_error_handler(request, error)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = []
    for item in exc.errors():
        loc = ".".join(str(part) for part in item.get("loc", ()))
        if loc:
            fields.append(loc)
    logger.info("%s %s -> %s %s", request.method, request.url.path, INTERNAL_VALIDATION_FAILED, fields)
    return _error_response(
        INTERNAL_VALIDATION_FAILED,
        ERROR_MESSAGES[INTERNAL_VALIDATION_FAILED],
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        {"fields": fields} if fields else None,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = HTTP_STATUS_CODES.get(exc.status_code, INTERNAL_ERROR)
    logger.info("%s %s -> HTTP %s 映射为 %s", request.method, request.url.path, exc.status_code, code)
    return _error_response(code, ERROR_MESSAGES[code], exc.status_code)


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "未处理异常 %s %s: %s: %s\n%s",
        request.method,
        request.url.path,
        type(exc).__name__,
        redact_sensitive_text(str(exc)),
        redact_sensitive_text(traceback.format_exc()),
    )
    return _error_response(
        INTERNAL_ERROR,
        ERROR_MESSAGES[INTERNAL_ERROR],
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册统一异常处理器；调用方需在 include_router 之后调用。"""

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(AllProvidersFailedError, all_providers_failed_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
