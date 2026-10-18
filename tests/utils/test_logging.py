import io
import json
import sys

import pytest
import structlog
from rich.console import Console
from rich.text import Text
from structlog.testing import ReturnLogger

import frame_compare.utils.logging as logging_module
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


@pytest.mark.parametrize(
    ("level", "prefix"),
    [("warning", "! "), ("error", "✗ "), ("critical", "✗ "), ("info", ""), ("debug", "")],
)
@pytest.mark.parametrize("no_color", [False, True])
def test_rich_log_format(
    monkeypatch: pytest.MonkeyPatch, level: str, prefix: str, no_color: bool
) -> None:
    output = io.StringIO()
    console = Console(file=output, force_terminal=True, color_system="standard", no_color=no_color)
    monkeypatch.setattr(logging_module, "human_console", lambda **kwargs: console)
    configure_logging(level="DEBUG", rich_output=True, no_color=no_color)

    getattr(structlog.get_logger(), level)("tmdb_lookup_failed", status=503, source="[red]clip")

    rendered = output.getvalue()
    assert Text.from_ansi(rendered).plain == (
        f"{prefix}tmdb lookup failed · source=[red]clip · status=503\n"
    )
    if no_color:
        assert "\x1b[33m" not in rendered
        assert "\x1b[31m" not in rendered
    else:
        assert "\x1b[2m" in rendered
        if prefix:
            assert ("\x1b[33m" if level == "warning" else "\x1b[31m") in rendered


@pytest.mark.parametrize("log_format", ["console", "json"])
def test_plain_and_json_log_renderers_remain_unchanged(
    monkeypatch: pytest.MonkeyPatch, log_format: str
) -> None:
    output = io.StringIO()
    monkeypatch.setattr(sys, "stderr", output)
    configure_logging(log_format=log_format, rich_output=log_format == "json")
    structlog.get_logger().warning("tmdb_lookup_failed", status=503)
    rendered = Text.from_ansi(output.getvalue()).plain
    if log_format == "json":
        payload = json.loads(rendered)
        assert payload["event"] == "tmdb_lookup_failed"
        assert payload["level"] == "warning"
        assert payload["timestamp"]
        assert payload["status"] == 503
    else:
        assert "[warning" in rendered
        assert "tmdb_lookup_failed" in rendered
        assert "status=503" in rendered


@pytest.mark.parametrize("rich_output", [False, True])
def test_exception_diagnostics_preserve_rendering(
    monkeypatch: pytest.MonkeyPatch, rich_output: bool
) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging(
        log_format="console" if rich_output else "json", rich_output=rich_output, no_color=True
    )
    api_key = "sentinel-tmdb-api-key"

    try:
        raise RuntimeError("lookup failed")
    except RuntimeError as exc:
        structlog.get_logger().warning("metadata_degraded", exc_info=exc)

    rendered = stream.getvalue()
    if rich_output:
        assert rendered.startswith("! metadata degraded\n")
        assert "Traceback" in rendered
        assert rendered.index("RuntimeError: lookup failed") > rendered.index("metadata degraded")
    else:
        payload = json.loads(rendered)
        assert payload["exception"]
        assert "locals" not in payload["exception"][0]["frames"][0]
        assert api_key not in json.dumps(payload)
