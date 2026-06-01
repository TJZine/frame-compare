import webbrowser
from pathlib import Path
from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from frame_compare.cli.entry import _maybe_open_report, app
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.config.loader import get_default_config
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult

from .cli_helpers import (
    MINIMAL_CONFIG,
    _invoke_run_with_minimal_workspace,
    _write_minimal_config,
    runner,
)


def test_run_opens_report_for_interactive_tty_when_auto_open_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    opened: dict[str, Path] = {}

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    assert opened["path"] == Path("report.html")


def test_run_does_not_open_report_when_auto_open_disabled_in_config(
    monkeypatch: MonkeyPatch,
) -> None:
    opened: dict[str, Path] = {}

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG + "\n[report]\nauto_open = false\n",
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
    assert "path" not in opened


def test_run_does_not_open_report_when_stdout_is_not_a_tty(monkeypatch: MonkeyPatch) -> None:
    opened: dict[str, Path] = {}

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: False)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    assert "path" not in opened


def test_run_does_not_open_report_when_quiet(monkeypatch: MonkeyPatch) -> None:
    opened: dict[str, Path] = {}

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace(["--quiet"])

    assert result.exit_code == 0
    assert "path" not in opened


def test_run_does_not_open_report_when_json_output_requested(monkeypatch: MonkeyPatch) -> None:
    opened: dict[str, Path] = {}

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace(["--json"])

    assert result.exit_code == 0
    assert "path" not in opened


def test_run_opens_report_when_post_run_config_reload_fails(monkeypatch: MonkeyPatch) -> None:
    opened: dict[str, Path] = {}
    load_calls = 0

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    def _load_config(_path: Path):
        nonlocal load_calls
        load_calls += 1
        if load_calls == 1:
            return get_default_config()
        raise ConfigNotFoundError(Path("missing.toml"))

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr("frame_compare.cli.entry.load_config", _load_config)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    assert load_calls == 2
    assert opened["path"] == Path("report.html")


def test_run_reloads_config_after_runner_and_respects_mid_run_auto_open_change(
    monkeypatch: MonkeyPatch,
) -> None:
    opened: dict[str, Path] = {}

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)

        def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
            config_path.write_text(
                MINIMAL_CONFIG + "\n[report]\nauto_open = false\n",
                encoding="utf-8",
            )
            return RunResult(
                success=True,
                screenshot_dir=Path("screenshots").resolve(),
                report_path=Path("report.html"),
            )

        monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
        monkeypatch.setattr(
            "frame_compare.cli.entry.sys",
            SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
        )
        monkeypatch.setattr(
            "frame_compare.cli.entry._maybe_open_report",
            lambda report_path: opened.setdefault("path", report_path),
        )

        result = runner.invoke(
            app,
            ["run", "--root", str(root), "--config", str(config_path.relative_to(root))],
            color=False,
            terminal_width=200,
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )

    assert result.exit_code == 0
    assert "path" not in opened


def test_run_slowpics_browser_open_suppresses_report_auto_open(
    monkeypatch: MonkeyPatch,
) -> None:
    opened_reports: dict[str, Path] = {}
    opened_urls: list[str] = []

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            slowpics_url="https://slow.pics/c/example",
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr("frame_compare.cli.entry._copy_text_to_clipboard", lambda _url: None)
    monkeypatch.setattr(
        "frame_compare.cli.entry._open_url_in_browser",
        lambda url: opened_urls.append(url) is None or True,
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened_reports.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    assert opened_urls == ["https://slow.pics/c/example"]
    assert "path" not in opened_reports


def test_run_report_auto_open_preserved_when_slowpics_browser_open_disabled(
    monkeypatch: MonkeyPatch,
) -> None:
    opened_reports: dict[str, Path] = {}
    opened_urls: list[str] = []

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            slowpics_url="https://slow.pics/c/example",
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr("frame_compare.cli.entry._copy_text_to_clipboard", lambda _url: None)
    monkeypatch.setattr(
        "frame_compare.cli.entry._open_url_in_browser",
        lambda url: opened_urls.append(url) is None or True,
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened_reports.setdefault("path", report_path),
    )

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG + "\n[slowpics]\nopen_in_browser = false\n",
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
    assert opened_urls == []
    assert opened_reports["path"] == Path("report.html")


def test_maybe_open_report_swallows_webbrowser_error(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("frame_compare.cli.cli_helpers.os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(
        "frame_compare.cli.cli_helpers.webbrowser.open",
        lambda _uri: (_ for _ in ()).throw(webbrowser.Error("no browser")),
    )

    _maybe_open_report(Path("report.html"))


def test_maybe_open_report_keeps_startfile_path_on_windows(monkeypatch: MonkeyPatch) -> None:
    called: dict[str, str] = {}
    fake_os = SimpleNamespace(
        name="nt",
        startfile=lambda value: called.setdefault("path", value),
    )
    monkeypatch.setattr("frame_compare.cli.cli_helpers.os", fake_os)
    monkeypatch.setattr(
        "frame_compare.cli.cli_helpers.webbrowser.open",
        lambda _uri: (_ for _ in ()).throw(AssertionError("webbrowser.open should not be called")),
    )

    _maybe_open_report(Path("report.html"))
    assert called["path"] == "report.html"


def test_maybe_open_report_falls_back_to_webbrowser_when_startfile_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    called: dict[str, str] = {}

    def _raise_startfile(_value: str) -> None:
        raise OSError("boom")

    fake_os = SimpleNamespace(name="nt", startfile=_raise_startfile)
    monkeypatch.setattr("frame_compare.cli.cli_helpers.os", fake_os)
    monkeypatch.setattr(
        "frame_compare.cli.cli_helpers.webbrowser.open",
        lambda uri: called.setdefault("uri", uri),
    )

    _maybe_open_report(Path("report.html"))

    assert called["uri"].startswith("file:")
