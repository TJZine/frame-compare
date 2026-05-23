from __future__ import annotations

import os
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from rich.console import Console

from frame_compare.cli.output import print_at_a_glance, print_result_summary
from frame_compare.config import ConfigSchema, get_default_config
from frame_compare.orchestration import RunRequest, RunResult


def _console() -> Console:
    return Console(record=True, no_color=True, width=200)


def _render(console: Console) -> str:
    return console.export_text(styles=False)


def _config() -> ConfigSchema:
    return get_default_config()


def _workspace_path(*parts: str) -> Path:
    return Path(os.path.sep, "workspace", *parts)


def _request(*, no_upload: bool = False) -> RunRequest:
    return RunRequest(root=_workspace_path(), no_upload=no_upload)


def test_at_a_glance_prints_key_rows_without_vspreview_probe(monkeypatch: MonkeyPatch) -> None:
    def _which(command: str) -> str | None:
        return f"/usr/bin/{command}" if command in {"ffmpeg", "ffprobe"} else None

    config = _config()
    config.screenshots.use_ffmpeg = True
    console = _console()

    monkeypatch.setattr("frame_compare.cli.output.shutil.which", _which)

    print_at_a_glance(
        console,
        request=_request(no_upload=True),
        config=config,
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    output = _render(console)
    assert "At-a-Glance" in output
    assert "root" in output
    assert str(_workspace_path()) in output
    assert "config" in output
    assert str(_workspace_path("config", "config.toml")) in output
    assert "input" in output
    assert "comparison_videos" in output
    assert "selection" in output
    assert "mixed, n=10, seed=42" in output
    assert "audio_alignment.ffmpeg_available" in output
    assert "audio_alignment.use_vspreview" in output
    assert "audio_alignment.force_interactive" in output
    assert "tonemap.preset" in output
    assert "reference" in output
    assert "renderer" in output
    assert "ffmpeg" in output
    assert "slow.pics.visibility" in output
    assert "unlisted" in output
    assert "report.auto_open" in output
    assert "upload" in output
    assert "disabled" in output
    assert "vspreview.available" not in output


def test_at_a_glance_prints_vspreview_availability_when_probe_succeeds(
    monkeypatch: MonkeyPatch,
) -> None:
    from frame_compare.vspreview.adapter import VSPreviewAvailability, VSPreviewAvailabilityStatus

    config = _config()
    config.audio_alignment.use_vspreview = True
    console = _console()

    monkeypatch.setattr("frame_compare.cli.output.shutil.which", lambda _command: None)
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.AVAILABLE,
            message="VSPreview is available for interactive alignment",
        ),
    )

    print_at_a_glance(
        console,
        request=_request(),
        config=config,
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    output = _render(console)
    assert "audio_alignment.use_vspreview" in output
    assert "vspreview.available" in output
    assert "true" in output


def test_at_a_glance_prints_vspreview_probe_failure(monkeypatch: MonkeyPatch) -> None:
    from frame_compare.vspreview.adapter import VSPreviewAvailability, VSPreviewAvailabilityStatus

    config = _config()
    config.audio_alignment.force_interactive = True
    console = _console()

    monkeypatch.setattr("frame_compare.cli.output.shutil.which", lambda _command: None)
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.PROBE_FAILED,
            message="VSPreview availability probe failed",
            error_details={
                "exception_type": "RuntimeError",
                "exception": "display unavailable",
            },
        ),
    )

    print_at_a_glance(
        console,
        request=_request(),
        config=config,
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    output = _render(console)
    assert "audio_alignment.force_interactive" in output
    assert "vspreview.available" in output
    assert "probe failed (RuntimeError: display unavailable)" in output


def test_result_summary_quiet_mode_prints_only_screenshot_path_when_available() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(success=True, screenshot_dir=_workspace_path("screenshots")),
        quiet=True,
    )

    output = _render(console)
    assert output.strip() == f"Screenshots: {_workspace_path('screenshots')}"

    empty_console = _console()
    print_result_summary(empty_console, result=RunResult(success=True), quiet=True)
    assert _render(empty_console) == ""


def test_result_summary_prints_artifact_rows_and_untruncated_warnings() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            screenshot_dir=_workspace_path("screenshots"),
            slowpics_url="https://slow.pics/c/example",
            report_path=_workspace_path("report.html"),
            warnings=["metadata skipped", "upload reused"],
        ),
        quiet=False,
    )

    output = _render(console)
    assert "Result" in output
    assert "screenshots" in output
    assert str(_workspace_path("screenshots")) in output
    assert "slow.pics" in output
    assert "https://slow.pics/c/example" in output
    assert "report" in output
    assert str(_workspace_path("report.html")) in output
    assert "Warnings" in output
    assert "- metadata skipped" in output
    assert "- upload reused" in output
    assert "more)" not in output


def test_result_summary_omits_warnings_panel_when_no_warnings_exist() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            screenshot_dir=_workspace_path("screenshots"),
            slowpics_url="https://slow.pics/c/example",
            report_path=_workspace_path("report.html"),
        ),
        quiet=False,
    )

    output = _render(console)
    assert "screenshots" in output
    assert "slow.pics" in output
    assert "report" in output
    assert "Warnings" not in output


def test_result_summary_prints_success_fallback_and_truncates_warnings() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            warnings=[f"warning {index}" for index in range(1, 11)],
        ),
        quiet=False,
    )

    output = _render(console)
    assert "Result" in output
    assert "status" in output
    assert "success" in output
    assert "Warnings" in output
    assert "- warning 1" in output
    assert "- warning 8" in output
    assert "- ... (2 more)" in output
    assert "warning 9" not in output
