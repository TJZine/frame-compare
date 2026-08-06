from __future__ import annotations

import webbrowser
from pathlib import Path
from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from frame_compare.cli.entry import _maybe_open_report, app
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult
from frame_compare.orchestration.types import SlowpicsUploadConfirmationRequest

from .cli_helpers import (
    MINIMAL_CONFIG,
    _invoke_run_with_minimal_workspace,
    _write_minimal_config,
    isolated_cli_filesystem,
    runner,
)


def test_run_opens_report_for_interactive_tty_when_auto_open_enabled(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    opened: list[Path] = []

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True, report_path=Path("report.html"))

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.append(report_path) is None,
    )

    result = _invoke_run_with_minimal_workspace([], tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert result.exit_code == 0
    assert opened == [Path("report.html")]


def test_run_reloads_config_after_runner_and_respects_auto_open_change(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    opened: list[Path] = []

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)

        def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
            config_path.write_text(
                MINIMAL_CONFIG + "\n[report]\nauto_open = false\n",
                encoding="utf-8",
            )
            return RunResult(success=True, report_path=Path("report.html"))

        monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
        monkeypatch.setattr(
            "frame_compare.cli.entry.sys",
            SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
        )
        monkeypatch.setattr(
            "frame_compare.cli.entry._maybe_open_report",
            lambda report_path: opened.append(report_path) is None,
        )

        result = runner.invoke(
            app,
            ["run", "--root", str(root), "--config", str(config_path.relative_to(root))],
            color=False,
            terminal_width=200,
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )

    assert result.exit_code == 0
    assert opened == []


def test_run_confirmed_slowpics_opens_report_before_later_slowpics_browser(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    opened_reports: list[Path] = []
    opened_urls: list[str] = []

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        assert dependencies is not None
        assert dependencies.confirm_slowpics_upload is not None
        decision = dependencies.confirm_slowpics_upload(
            SlowpicsUploadConfirmationRequest(report_path=Path("report.html"))
        )
        return RunResult(
            success=True,
            slowpics_url="https://slow.pics/c/example",
            report_path=Path("report.html"),
            slowpics_upload_confirmation_status=decision,
        )

    def _confirm_upload(_text: str, *, default: bool) -> bool:
        assert default is False
        assert opened_reports == [Path("report.html")]
        events.append("prompt")
        return True

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(
            stdin=SimpleNamespace(isatty=lambda: True),
            stdout=SimpleNamespace(isatty=lambda: True),
        ),
    )
    monkeypatch.setattr("frame_compare.cli.entry.typer.confirm", _confirm_upload)
    monkeypatch.setattr("frame_compare.cli.entry._copy_text_to_clipboard", lambda _url: None)
    monkeypatch.setattr(
        "frame_compare.cli.entry._open_url_in_browser",
        lambda url: opened_urls.append(url) is None or True,
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened_reports.append(report_path) is None,
    )

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG
            + "\n[slowpics]\nauto_upload = true\nconfirm_upload_after_report = true\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["run", "--root", str(root), "--config", str(config_path.relative_to(root))],
            color=False,
            terminal_width=200,
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )

    assert result.exit_code == 0
    assert events == ["prompt"]
    assert opened_reports == [Path("report.html")]
    assert opened_urls == ["https://slow.pics/c/example"]


def test_maybe_open_report_swallows_webbrowser_error(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("frame_compare.cli.cli_helpers.os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(
        "frame_compare.cli.cli_helpers.webbrowser.open",
        lambda _uri: (_ for _ in ()).throw(webbrowser.Error("no browser")),
    )

    assert _maybe_open_report(Path("report.html")) is False


def test_maybe_open_report_returns_false_when_no_browser_accepts(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("frame_compare.cli.cli_helpers.os", SimpleNamespace(name="posix"))
    monkeypatch.setattr("frame_compare.cli.cli_helpers.webbrowser.open", lambda _uri: False)

    assert _maybe_open_report(Path("report.html")) is False


def test_maybe_open_report_keeps_startfile_path_on_windows(monkeypatch: MonkeyPatch) -> None:
    called: dict[str, str] = {}
    fake_os = SimpleNamespace(name="nt", startfile=lambda value: called.setdefault("path", value))
    monkeypatch.setattr("frame_compare.cli.cli_helpers.os", fake_os)
    monkeypatch.setattr(
        "frame_compare.cli.cli_helpers.webbrowser.open",
        lambda _uri: (_ for _ in ()).throw(AssertionError("webbrowser.open should not be called")),
    )

    assert _maybe_open_report(Path("report.html")) is True
    assert called["path"] == "report.html"


def test_maybe_open_report_falls_back_to_webbrowser_when_startfile_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    called: dict[str, str] = {}

    def _raise_startfile(_value: str) -> None:
        raise OSError("boom")

    monkeypatch.setattr(
        "frame_compare.cli.cli_helpers.os",
        SimpleNamespace(name="nt", startfile=_raise_startfile),
    )
    monkeypatch.setattr(
        "frame_compare.cli.cli_helpers.webbrowser.open",
        lambda uri: called.setdefault("uri", uri) is not None,
    )

    assert _maybe_open_report(Path("report.html")) is True
    assert called["uri"].startswith("file:")
