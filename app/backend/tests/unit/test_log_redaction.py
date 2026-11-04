"""后端-单元：日志脱敏不得破坏 uvicorn 访问日志的 args 结构。

历史 bug：过滤器无条件把 ``record.args`` 置空，而 uvicorn 的 AccessFormatter 会
把访问日志 args 当成 5 元组解包，导致每条访问日志抛
``ValueError: not enough values to unpack (expected 5, got 0)``。
这些用例在修复前会真实失败（handler 管道拿不到日志行、stderr 出现堆栈）。
"""

import contextlib
import io
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from uvicorn.logging import AccessFormatter

from core.log_redaction import SensitiveDataFilter, redact_sensitive_text

# 与 uvicorn httptools_impl 访问日志完全一致的模板与 5 元组参数。
_ACCESS_TEMPLATE = '%s - "%s %s HTTP/%s" %d'
_ACCESS_ARGS = ("10.0.0.1", "GET", "/health?token=abc123456", "1.1", 200)
_ACCESS_FORMAT = '%(client_addr)s - "%(request_line)s" %(status_code)s'


def _access_record(args=_ACCESS_ARGS):
    return logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, _ACCESS_TEMPLATE, args, None
    )


def _attached_access_logger(stream: io.StringIO):
    """把带 AccessFormatter + 脱敏过滤器的 handler 挂到真实的 uvicorn.access。"""
    logger = logging.getLogger("uvicorn.access")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(AccessFormatter(_ACCESS_FORMAT))
    handler.addFilter(SensitiveDataFilter())
    previous = (list(logger.handlers), logger.propagate, logger.level)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger, previous


def _restore(logger, previous):
    handlers, propagate, level = previous
    logger.handlers = handlers
    logger.propagate = propagate
    logger.setLevel(level)


def test_access_record_keeps_five_args_after_filter():
    record = _access_record()
    SensitiveDataFilter().filter(record)

    assert isinstance(record.args, tuple)
    assert len(record.args) == 5
    assert record.args[0] == "10.0.0.1"
    assert record.args[4] == 200  # 非字符串原样保留，AccessFormatter 需要 int 状态码
    # 查询串里的 token 仍然必须被脱敏（不能因为保留结构就放弃脱敏）。
    assert "abc123456" not in record.args[2]


def test_access_formatter_formats_redacted_record_with_status_code():
    record = _access_record()
    SensitiveDataFilter().filter(record)

    formatted = AccessFormatter(_ACCESS_FORMAT).format(record)

    assert "200 OK" in formatted
    assert 'GET /health?token=[已隐藏]' in formatted


def test_application_access_log_emits_line_without_unpack_error():
    """应用级：真实 uvicorn.access logger + AccessFormatter + 过滤器管道。"""
    stream = io.StringIO()
    stderr = io.StringIO()
    logger, previous = _attached_access_logger(stream)
    try:
        with contextlib.redirect_stderr(stderr):
            logger.info(_ACCESS_TEMPLATE, *_ACCESS_ARGS)
    finally:
        _restore(logger, previous)

    assert "200" in stream.getvalue()
    assert "abc123456" not in stream.getvalue()
    assert "not enough values to unpack" not in stderr.getvalue()
    assert "Logging error" not in stderr.getvalue()


def test_testclient_request_has_no_unpack_error():
    """TestClient 发起真实请求；请求期间日志管道不得出现解包堆栈。"""
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    stream = io.StringIO()
    stderr = io.StringIO()
    logger, previous = _attached_access_logger(stream)
    try:
        with contextlib.redirect_stderr(stderr):
            response = TestClient(app).get("/health")
            # TestClient 不经过 uvicorn server，这里补发一条同形状访问记录，
            # 覆盖线上真正出问题的那条日志通路。
            logger.info(_ACCESS_TEMPLATE, *_ACCESS_ARGS)
    finally:
        _restore(logger, previous)

    assert response.status_code == 200
    assert "200" in stream.getvalue()
    assert "not enough values to unpack" not in stderr.getvalue()


def test_secrets_still_masked_after_expansion():
    record = logging.LogRecord(
        "app",
        logging.INFO,
        __file__,
        1,
        "连接 %s，使用 sk-%s",
        ("postgresql://user:pass@host/db", "abcdef1234567890"),
        None,
    )
    SensitiveDataFilter().filter(record)

    message = record.getMessage()
    assert "user:pass@" not in message
    assert "sk-abcdef1234567890" not in message


def test_redact_covers_ark_keys_and_authorization():
    raw = (
        "key=ark-abcdefghijklmnopqrstuvwxyz "
        "Authorization: Bearer abcdefgh12345678 "
        "postgresql://user:pass@host/db"
    )

    cleaned = redact_sensitive_text(raw)

    assert "ark-abcdefghijklmnopqrstuvwxyz" not in cleaned
    assert "abcdefgh12345678" not in cleaned
    assert "user:pass@" not in cleaned
