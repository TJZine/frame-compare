from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from _pytest.monkeypatch import MonkeyPatch
from rich.console import Console

from frame_compare.cli.output import (
    PostUploadActionPresentationResult,
    print_at_a_glance,
    print_result_summary,
)
from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import AnalysisPerformanceMode, ConfigSchema
from frame_compare.orchestration import RunRequest, RunResult


def _console() -> Console:
    return Console(record=True, no_color=True, width=200)


def _render(console: Console) -> str:
    return console.export_text(styles=False)


def _rendered_row_value(output: str, row_label: str) -> str:
    for line in output.splitlines():
        if row_label in line:
            return line
    raise AssertionError(f"Missing row label: {row_label}")


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
    assert str(_workspace_path("comparison_videos")) in output
    assert "run folders" in output
    assert "base paths" in output
    assert "selection" in output
    assert "user=0, random=10, dark=0, bright=0, motion=0, seed=42" in output
    assert "analysis mode" in output
    assert "quality" in _rendered_row_value(output, "analysis mode")
    assert "FFmpeg audio" in output
    assert "previous offsets" in output
    assert "disabled" in output
    assert "interactive alignment" in output
    assert "force interactive" in output
    assert "tonemap.preset" in output
    assert "reference" in output
    assert "renderer" in output
    assert "ffmpeg" in output
    assert "slow.pics" in output
    assert "visibility" in output
    assert "public" in output
    assert "report" in output
    assert "auto_open" in output
    assert "upload" in output
    assert "disabled" in output
    assert "VSPreview" not in output


def test_at_a_glance_prints_previous_offsets_effective_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("frame_compare.cli.output.shutil.which", lambda _command: None)
    modes: tuple[Literal["disabled", "prompt", "always"], ...] = ("disabled", "prompt", "always")

    for mode in modes:
        config = _config()
        config.audio_alignment.previous_offsets = mode
        console = _console()

        print_at_a_glance(
            console,
            request=_request(),
            config=config,
            root=_workspace_path(),
            config_path=_workspace_path("config", "config.toml"),
        )

        output = _render(console)
        previous_offsets_row = _rendered_row_value(output, "previous offsets")
        assert mode in previous_offsets_row


def test_at_a_glance_prints_effective_analysis_performance_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    config = _config()
    config.analysis.performance_mode = AnalysisPerformanceMode.PERFORMANCE
    console = _console()

    monkeypatch.setattr("frame_compare.cli.output.shutil.which", lambda _command: None)

    print_at_a_glance(
        console,
        request=_request(),
        config=config,
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    analysis_mode_row = _rendered_row_value(_render(console), "analysis mode")
    assert "performance" in analysis_mode_row


def test_at_a_glance_preserves_literal_brackets_in_dynamic_paths(
    monkeypatch: MonkeyPatch,
) -> None:
    config = _config()
    config.paths.input_dir = Path("[bold]input[end]")
    config.paths.screenshots_dir = Path("[red]screens[end]")
    config.paths.generated_dir = Path("[cyan]generated[end]")
    console = _console()

    monkeypatch.setattr("frame_compare.cli.output.shutil.which", lambda _command: None)

    print_at_a_glance(
        console,
        request=_request(),
        config=config,
        root=_workspace_path("[root]"),
        config_path=_workspace_path("config", "[file].toml"),
    )

    output = _render(console)
    assert "root" in output
    assert str(_workspace_path("[root]")) in output
    assert str(_workspace_path("config", "[file].toml")) in output
    assert "[bold]input[end]" in output
    assert "[red]screens[end]" in output
    assert "[cyan]generated[end]" in output


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
    assert "interactive alignment" in output
    assert "VSPreview" in output
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
    assert "force interactive" in output
    assert "VSPreview" in output
    assert "probe failed (RuntimeError)" in output
    assert "display unavailable" not in output


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
    assert "metadata skipped" in output
    assert "upload reused" in output
    assert "more)" not in output


def test_result_summary_prints_declined_slowpics_as_skipped_not_artifact() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            slowpics_upload_confirmation_status="declined",
            report_path=_workspace_path("report.html"),
        ),
        quiet=False,
    )

    output = _render(console)
    assert "slow.pics upload skipped by confirmation" in output
    assert "✓ slow.pics" not in output
    assert "- slow.pics" in output


def test_result_summary_prints_report_unavailable_slowpics_as_skipped() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            slowpics_upload_confirmation_status="report_unavailable",
        ),
        quiet=False,
    )

    output = _render(console)
    assert "slow.pics upload skipped because report confirmation was unavailable" in output
    assert "✓ slow.pics" not in output
    assert "- slow.pics" in output


def test_result_summary_groups_warning_sources_with_severity_detail_and_action() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            warnings=[
                "align: encode_b low confidence; left unapplied and untrimmed",
                "slow.pics upload skipped because report confirmation was unavailable",
                "align: encode_c low confidence; left unapplied and untrimmed",
            ],
        ),
        quiet=False,
        post_upload_actions=(
            PostUploadActionPresentationResult(
                kind="clipboard",
                success=False,
                warning="slow.pics clipboard: failed to copy URL: clipboard unavailable",
            ),
        ),
    )

    output = _render(console)
    assert "alignment" in output
    assert "slow.pics" in output
    assert output.count("alignment") == 1
    assert "align: encode_b low confidence; left unapplied and untrimmed (warning)" in output
    assert "align: encode_c low confidence; left unapplied and untrimmed (warning)" in output
    assert (
        "slow.pics upload skipped because report confirmation was unavailable (skipped)" in output
    )
    assert "detail because report confirmation was unavailable" in output
    assert "action clipboard" in output
    assert output.index("encode_c") < output.index("slow.pics upload skipped")


def test_result_summary_preserves_literal_brackets_in_dynamic_values() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            screenshot_dir=_workspace_path("screenshots", "[episode]"),
            slowpics_url="https://slow.pics/c/[example]",
            report_path=_workspace_path("reports", "[episode].html"),
            warnings=["metadata [skipped]"],
        ),
        quiet=False,
    )

    output = _render(console)
    assert str(_workspace_path("screenshots", "[episode]")) in output
    assert "https://slow.pics/c/[example]" in output
    assert str(_workspace_path("reports", "[episode].html")) in output
    assert "metadata [skipped]" in output


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


def test_result_summary_reports_skipped_analysis_cache_status() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            frame_count=1,
            clips_processed=2,
            duration_seconds=0.5,
            cache_hit=False,
            metrics_cache_status="skipped",
        ),
        quiet=False,
    )

    output = _render(console)
    assert "cache" in output
    assert "skipped" in output
    assert "miss" not in output


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
    assert "warning 1" in output
    assert "warning 8" in output
    assert "(2 more)" in output
    assert "warning 9" not in output


def test_result_summary_quiet_mode_preserves_literal_brackets() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(success=True, screenshot_dir=_workspace_path("screenshots", "[episode]")),
        quiet=True,
    )

    output = _render(console).strip()
    assert output.startswith("Screenshots:")
    assert str(_workspace_path("screenshots", "[episode]")) in output
