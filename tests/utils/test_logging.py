import io
import json
import sys

import pytest
import structlog
from structlog.testing import ReturnLogger

from frame_compare.utils.logging import configure_logging


def test_configure_logging_json_format():
    """Test that configure_logging with log_format='json' adds JSONRenderer."""
    configure_logging(log_format="json")
    config = structlog.get_config()
    processors = config["processors"]
    assert any(isinstance(p, structlog.processors.JSONRenderer) for p in processors)


def test_configure_logging_console_format():
    """Test that configure_logging with log_format='console' adds ConsoleRenderer."""
    configure_logging(log_format="console")
    config = structlog.get_config()
    processors = config["processors"]
    assert any(isinstance(p, structlog.dev.ConsoleRenderer) for p in processors)


def test_configure_logging_unknown_format_falls_back_to_console():
    """Test that configure_logging with unknown format falls back to console."""
    configure_logging(log_format="invalid")
    config = structlog.get_config()
    processors = config["processors"]
    assert any(isinstance(p, structlog.dev.ConsoleRenderer) for p in processors)


def test_configure_logging_level_filtering_warning():
    """WARNING level: INFO filtered, WARNING allowed."""
    configure_logging(level="WARNING")
    config = structlog.get_config()
    wrapper_class = config["wrapper_class"]
    log = structlog.wrap_logger(
        ReturnLogger(),
        wrapper_class=wrapper_class,
        processors=[structlog.processors.add_log_level],
    )
    assert log.info("test") is None  # filtered
    assert log.warning("test") is not None  # allowed


def test_configure_logging_unknown_level_falls_back_to_info():
    """Unknown level falls back to INFO: DEBUG filtered, INFO allowed."""
    configure_logging(level="INVALID")
    config = structlog.get_config()
    wrapper_class = config["wrapper_class"]
    log = structlog.wrap_logger(
        ReturnLogger(),
        wrapper_class=wrapper_class,
        processors=[structlog.processors.add_log_level],
    )
    assert log.debug("test") is None  # filtered
    assert log.info("test") is not None  # allowed


def test_logging_accepts_stream_write_returning_none(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoneReturningStderr:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def write(self, message: str) -> None:
            self.messages.append(message)

        def flush(self) -> None:
            return None

    stream = NoneReturningStderr()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging()

    structlog.get_logger().info("message")

    assert "message" in "".join(stream.messages)


def test_logging_uses_current_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_logging()
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)

    structlog.get_logger().info("late bound")

    assert "late bound" in stream.getvalue()


def test_logging_falls_back_when_stderr_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fallback)
    configure_logging()
    monkeypatch.setattr(sys, "stderr", None)

    structlog.get_logger().info("shutdown")

    assert "shutdown" in fallback.getvalue()


def test_repeated_configuration_replaces_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging(log_format="console")
    configure_logging(log_format="json")

    structlog.get_logger().info("message")

    assert json.loads(stream.getvalue())["event"] == "message"
