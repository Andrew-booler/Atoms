"""日志脱敏工具：避免 DB URL、AI key、Authorization、artifact 全文进入日志。"""

import logging
import re

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # postgresql://user:password@host -> postgresql://[已隐藏]@host
    (re.compile(r"(?i)\b((?:postgresql|mysql|redis|mongodb)(?:\+\w+)?://)[^\s/@]+@"), r"\1[已隐藏]@"),
    # Authorization: Bearer xxx / token
    (re.compile(r"(?i)\b(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+"), r"\1[已隐藏]"),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._\-+/=]{8,}"), r"\1[已隐藏]"),
    # api_key / token / secret / password 字段
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|secret|password|token)\b(\s*[:=]\s*)[\"']?[^\s\"',}]{6,}"
        ),
        r"\1\2[已隐藏]",
    ),
    # 常见供应商明文 key 前缀
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"), "[已隐藏]"),
)

_MAX_LOG_CHARS = 4000


def redact_sensitive_text(text: str) -> str:
    """对日志文本做敏感信息替换与长度截断。"""

    redacted = text
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    if len(redacted) > _MAX_LOG_CHARS:
        redacted = redacted[:_MAX_LOG_CHARS] + "...(日志已截断)"
    return redacted


class SensitiveDataFilter(logging.Filter):
    """全局日志过滤器：清洗消息与异常堆栈，避免密钥/DB URL/超长正文落盘。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - 异常参数格式化兜底
            message = str(record.msg)
        record.msg = redact_sensitive_text(message)
        record.args = ()
        if record.exc_info:
            record.exc_text = redact_sensitive_text(
                logging.Formatter().formatException(record.exc_info)
            )
        return True


def install_sensitive_data_filter() -> None:
    """把过滤器挂到 root 与 uvicorn/fastapi 的现有 handler 上。"""

    filter_instance = SensitiveDataFilter()
    loggers = (logging.getLogger(),) + tuple(
        logging.getLogger(name) for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi")
    )
    for logger in loggers:
        for handler in logger.handlers:
            if not any(isinstance(item, SensitiveDataFilter) for item in handler.filters):
                handler.addFilter(filter_instance)
