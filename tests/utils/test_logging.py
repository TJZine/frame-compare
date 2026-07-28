import io
import json
import re
import sys

import pytest
import structlog
from structlog.testing import ReturnLogger

import frame_compare.utils.logging as logging_module
from frame_compare.utils.logging import configure_logging, get_run_id, new_run_id


@pytest.fixture(autouse=True)
def reset_logging_state():
    """Reset structlog config and module ContextVar before each test."""
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    logging_module._run_id.set("")  # pyright: ignore[reportPrivateUsage]
    yield
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    logging_module._run_id.set("")  # pyright: ignore[reportPrivateUsage]


def test_new_run_id_returns_8_char_hex():
    """Test that new_run_id returns an 8-character hex string."""
    result = new_run_id()
    assert re.fullmatch(r"[0-9a-f]{8}", result)


def test_new_run_id_sets_context_var():
    """Test that new_run_id sets the module-level ContextVar."""
    run_id = new_run_id()
    assert get_run_id() == run_id


def test_new_run_id_binds_to_structlog_contextvars():
    """Test that new_run_id binds the ID to structlog contextvars."""
    run_id = new_run_id()
    assert structlog.contextvars.get_contextvars()["run_id"] == run_id


def test_get_run_id_default_unknown():
    """Test that get_run_id returns 'unknown' if no ID is set."""
    assert get_run_id() == "unknown"


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
