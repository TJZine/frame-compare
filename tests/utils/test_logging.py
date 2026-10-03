import io
import json
import sys

import pytest
import structlog
from structlog.testing import ReturnLogger

from frame_compare.utils.logging import configure_logging


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


@pytest.mark.parametrize(
    ("mode", "message"),
    [("none-return", "message"), ("late-bound", "late bound"), ("shutdown", "shutdown")],
)
def test_logging_handles_stderr_lifecycle(
    monkeypatch: pytest.MonkeyPatch, mode: str, message: str
) -> None:
    class NoneReturningStderr:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def write(self, value: str) -> None:
            self.messages.append(value)

        def flush(self) -> None:
            return None

    if mode == "late-bound":
        configure_logging()
    stream = NoneReturningStderr() if mode == "none-return" else io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    if mode != "late-bound":
        configure_logging()
    if mode == "shutdown":
        monkeypatch.setattr(sys, "stderr", None)
    structlog.get_logger().info(message)
    rendered = (
        "".join(stream.messages) if isinstance(stream, NoneReturningStderr) else stream.getvalue()
    )
    assert message in rendered


def test_repeated_configuration_replaces_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging(log_format="console")
    configure_logging(log_format="json")

    structlog.get_logger().info("message")

    assert json.loads(stream.getvalue())["event"] == "message"


def test_json_exception_diagnostics_do_not_capture_locals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging(log_format="json")
    api_key = "sentinel-tmdb-api-key"

    try:
        raise RuntimeError("lookup failed")
    except RuntimeError as exc:
        structlog.get_logger().warning("metadata_degraded", exc_info=exc)

    payload = json.loads(stream.getvalue())
    assert payload["exception"]
    assert "locals" not in payload["exception"][0]["frames"][0]
    assert api_key not in json.dumps(payload)
