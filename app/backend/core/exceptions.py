"""统一业务异常体系。

对外契约：{"code": DOMAIN_REASON, "message": 中文可读文案, "details": {...}?}
- code 一码一义，定义见 core/error_codes.py
- message 只放用户可读中文，禁止拼接堆栈或原始异常
- details 仅放结构化辅助信息，写入前统一脱敏
"""

from typing import Any

from core import error_codes
from core.log_redaction import redact_sensitive_text

_SECRET_KEYS = (
    "key",
    "token",
    "secret",
    "password",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
)


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_KEYS)


def sanitize_details(value: Any, *, _depth: int = 0) -> Any:
    """递归脱敏 details：隐藏密钥字段、截断超长文本，避免日志/响应泄露。"""

    if _depth > 6:
        return "[已省略]"
    if isinstance(value, dict):
        return {
            str(k): ("[已隐藏]" if _is_secret_key(str(k)) else sanitize_details(v, _depth=_depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_details(item, _depth=_depth + 1) for item in value]
    if isinstance(value, str):
        cleaned = redact_sensitive_text(value)
        return cleaned if len(cleaned) <= 500 else cleaned[:500] + "...(已截断)"
    return value


class AppError(Exception):
    """业务异常基类。子类只负责默认分级，错误码与文案来自 error_codes。"""

    code: str = error_codes.INTERNAL_ERROR
    http_status: int = 500
    retryable: bool = False

    def __init__(
        self,
        code: str | None = None,
        message: str | None = None,
        *,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
    ) -> None:
        resolved_code = code or self.code
        resolved_message = message or error_codes.ERROR_MESSAGES.get(
            resolved_code, error_codes.ERROR_MESSAGES[error_codes.INTERNAL_ERROR]
        )
        self.code = resolved_code
        self.message = resolved_message
        self.http_status = http_status if http_status is not None else self.http_status
        self.details = sanitize_details(details) if details else None
        self.retryable = self.retryable if retryable is None else retryable
        super().__init__(f"{self.code}: {self.message}")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationError(AppError):
    code = error_codes.INTERNAL_VALIDATION_FAILED
    http_status = 422


class NotFoundError(AppError):
    code = error_codes.RESOURCE_NOT_FOUND
    http_status = 404


class ConflictError(AppError):
    code = error_codes.INTERNAL_STATE_CONFLICT
    http_status = 409


class RateLimitError(AppError):
    code = error_codes.RATE_LIMITED
    http_status = 429
    retryable = True


class PayloadTooLargeError(AppError):
    code = error_codes.PAYLOAD_TOO_LARGE
    http_status = 413


class AuthError(AppError):
    code = error_codes.AUTH_REQUIRED
    http_status = 401


class ProviderError(AppError):
    code = error_codes.INTERNAL_PROVIDER_FAILED
    http_status = 502
    retryable = True


class SandboxUnavailableError(AppError):
    code = error_codes.SANDBOX_DOCKER_UNAVAILABLE
    http_status = 503
    retryable = True


class InternalError(AppError):
    code = error_codes.INTERNAL_ERROR
    http_status = 500
