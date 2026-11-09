from __future__ import annotations

import os
import shlex
from pathlib import Path
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch

from frame_compare.cli.cli_helpers import copy_text_to_clipboard, open_url_in_browser
from frame_compare.cli.entry import _maybe_open_report, app
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult
from frame_compare.orchestration.types import SlowpicsUploadConfirmationRequest

from .cli_helpers import (
    MINIMAL_CONFIG,
    _write_minimal_config,
    isolated_cli_filesystem,
    runner,
)


@pytest.mark.parametrize("change_config", [False, True], ids=["enabled", "disabled-after-run"])
def test_run_report_auto_open_reloads_config(
    monkeypatch: MonkeyPatch, tmp_path: Path, change_config: bool
) -> None:
    opened: list[Path] = []
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)

        def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
            if change_config:
                config_path.write_text(
                    MINIMAL_CONFIG + "\n[report]\nauto_open = false\n", encoding="utf-8"
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
    assert opened == ([] if change_config else [Path("report.html")])


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
    assert opened_reports == [Path("report.html")]
    assert opened_urls == ["https://slow.pics/c/example"]


@pytest.mark.skipif(os.name != "posix", reason="Uses a local POSIX browser command")
def test_desktop_opener_preserves_default_browser_and_filters_credentials(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "browser-result"
    browser = tmp_path / "fixture-browser"
    browser.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$1" "${FRAME_COMPARE_TMDB__API_KEY-unset}" '
        '"${FRAME_COMPARE_TMDB-unset}" "${FRAME_COMPARE_SLOWPICS-unset}" '
        '"$VAPOURSYNTH_EXTRA_PLUGIN_PATH" > "$FRAME_COMPARE_TEST_BROWSER_RESULT"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    browser.chmod(0o700)
    monkeypatch.setenv("BROWSER", f"{shlex.quote(str(browser))} %s")
    monkeypatch.setenv("FRAME_COMPARE_TEST_BROWSER_RESULT", str(marker))
    monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "synthetic-browser-secret")
    monkeypatch.setenv("FRAME_COMPARE_TMDB", '{"api_key":"synthetic-browser-section-key"}')
    monkeypatch.setenv("FRAME_COMPARE_SLOWPICS", '{"webhook_url":"synthetic-browser-section-hook"}')
    monkeypatch.setenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", "synthetic-plugin-path")
    report = tmp_path / "report.html"
    assert _maybe_open_report(report)
    assert marker.read_text().splitlines() == [
        report.resolve().as_uri(),
        "unset",
        "unset",
        "unset",
        "synthetic-plugin-path",
    ]


@pytest.mark.skipif(os.name != "posix", reason="Uses a local POSIX browser command")
def test_browser_handler_can_finish_after_desktop_broker_exits(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    release = tmp_path / "release"
    marker = tmp_path / "completed"
    browser = tmp_path / "background-browser"
    browser.write_text(
        "#!/bin/sh\n"
        "(\n"
        "    attempts=0\n"
        '    until [ -e "$2" ]; do\n'
        '        [ "$attempts" -lt 100 ] || exit 1\n'
        "        attempts=$((attempts + 1))\n"
        "        sleep 0.05\n"
        "    done\n"
        '    touch "$3"\n'
        ") &\n"
        "exit 0\n",
        encoding="utf-8",
    )
    browser.chmod(0o700)
    monkeypatch.setenv("BROWSER", shlex.join([str(browser), "%s", str(release), str(marker)]))

    assert open_url_in_browser("https://slow.pics/c/example")
    assert not marker.exists()
    release.touch()
    deadline = monotonic() + 3.0
    while not marker.exists() and monotonic() < deadline:
        sleep(0.01)
    assert marker.exists()


@pytest.mark.skipif(os.name != "posix", reason="Uses a local POSIX browser command")
def test_browser_action_times_out_and_reaps_broker(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "broker-pid"
    browser = tmp_path / "blocking-browser"
    browser.write_text(
        "#!/bin/sh\n"
        'broker_pid="$PPID"\n'
        'printf "%s\\n" "$broker_pid" > "$2"\n'
        "attempts=0\n"
        'while kill -0 "$broker_pid" 2>/dev/null && [ "$attempts" -lt 100 ]; do\n'
        "    attempts=$((attempts + 1))\n"
        "    sleep 0.05\n"
        "done\n",
        encoding="utf-8",
    )
    browser.chmod(0o700)
    monkeypatch.setenv("BROWSER", shlex.join([str(browser), "%s", str(marker)]))
    monkeypatch.setattr("frame_compare.cli.cli_helpers._DESKTOP_ACTION_TIMEOUT_SECONDS", 1.0)

    assert not open_url_in_browser("https://slow.pics/c/example")
    with pytest.raises(ProcessLookupError):
        os.kill(int(marker.read_text()), 0)


def test_browser_and_clipboard_reject_unsafe_publication_urls(monkeypatch: MonkeyPatch) -> None:
    launch = Mock(side_effect=AssertionError("Must reject URL before desktop launch"))
    monkeypatch.setattr("frame_compare.cli.cli_helpers._run_desktop_action", launch)
    for action in (open_url_in_browser, copy_text_to_clipboard):
        with pytest.raises(ValueError, match="canonical"):
            action("https://slow.pics/c/id\nURL=https://example.test")
    launch.assert_not_called()
