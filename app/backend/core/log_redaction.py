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
    # 常见供应商明文 key 前缀（sk- / ark- 类）
    (re.compile(r"\b(?:sk|ark)-[A-Za-z0-9_\-]{12,}"), "[已隐藏]"),
)

_MAX_LOG_CHARS = 4000

#: uvicorn 访问日志的 logger 名；其 args 是 AccessFormatter 的解包输入，不可改变形状。
_ACCESS_LOGGER_NAME = "uvicorn.access"


def _redact_arg(value: object) -> object:
    """按项脱敏：仅处理字符串，其它类型（状态码等）原样保留。"""
    return redact_sensitive_text(value) if isinstance(value, str) else value


def redact_sensitive_text(text: str) -> str:
    """对日志文本做敏感信息替换与长度截断。"""

    redacted = text
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    if len(redacted) > _MAX_LOG_CHARS:
        redacted = redacted[:_MAX_LOG_CHARS] + "...(日志已截断)"
    return redacted


class SensitiveDataFilter(logging.Filter):
    """全局日志过滤器：清洗消息、参数与异常堆栈，避免密钥/DB URL/超长正文落盘。

    关键约束：``record.args`` 必须保持原有类型与长度。uvicorn 的 AccessFormatter
    会把访问日志的 args 当成 5 元组 (client_addr, method, path, http_version, status)
    直接解包，历史上无条件清空 args 会导致每条访问日志都抛
    ``ValueError: not enough values to unpack (expected 5, got 0)``。
    因此这里改为逐项脱敏，仅在非访问日志且格式化后仍命中敏感规则时折叠为纯文本。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        # 逐项脱敏，保持元组/字典的结构与元素类型（非字符串原样保留）。
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_arg(item) for item in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: _redact_arg(item) for key, item in record.args.items()}
        elif isinstance(record.args, str):
            record.args = _redact_arg(record.args)

        # 展开后再兜底匹配一次：参数与模板拼接后仍含敏感串时，非访问日志改为
        # 纯文本输出；访问日志不能清空 args，逐项脱敏已覆盖其全部动态字符串。
        if record.name != _ACCESS_LOGGER_NAME:
            try:
                message = record.getMessage()
            except Exception:  # pragma: no cover - 异常参数格式化兜底
                message = None
            if message is not None:
                redacted = redact_sensitive_text(message)
                if redacted != message:
                    record.msg = redacted
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
