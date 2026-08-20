from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

import pytest
from _pytest.monkeypatch import MonkeyPatch
from rich.console import Console

from frame_compare.cli.output import (
    PostUploadActionPresentationResult,
    print_at_a_glance,
    print_result_summary,
)
from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import AnalysisPerformanceMode, ConfigSchema
from frame_compare.config.schema_enums import (
    OverlayMode,
    ScreenshotActiveRectDetection,
    ScreenshotGeometryMode,
    Visibility,
)
from frame_compare.orchestration import RunRequest, RunResult


def _console() -> Console:
    return Console(record=True, no_color=True, width=200)


def _console_at_width(width: int) -> Console:
    return Console(record=True, no_color=True, width=width)


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


def _request(*, no_upload: bool = False, skip_analysis: bool = False) -> RunRequest:
    return RunRequest(
        root=_workspace_path(),
        no_upload=no_upload,
        skip_analysis=skip_analysis,
    )


def _missing_executable(_name: str) -> str:
    raise FileNotFoundError(_name)


def test_at_a_glance_prints_key_rows_without_vspreview_probe(monkeypatch: MonkeyPatch) -> None:
    def _resolve(command: str) -> str:
        if command not in {"ffmpeg", "ffprobe"}:
            raise FileNotFoundError(command)
        return f"/usr/bin/{command}"

    config = _config()
    config.screenshots.use_ffmpeg = True
    console = _console()

    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _resolve)

    print_at_a_glance(
        console,
        request=_request(no_upload=True),
        config=config,
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    output = _render(console)
    assert "Run plan" in output
    assert str(_workspace_path()) in _rendered_row_value(output, "root")
    assert str(Path("config") / "config.toml") in _rendered_row_value(output, "config")
    assert "comparison_videos" in _rendered_row_value(output, "input")
    assert "generated" in _rendered_row_value(output, "generated")
    assert "run folders" not in output
    assert "screenshots" not in output
    assert "requested" in output
    assert "user=0, random=10, dark=0, bright=0, motion=0" in output
    assert "seed" in output
    assert "quality" in _rendered_row_value(output, "analysis mode")
    assert "true" in _rendered_row_value(output, "FFmpeg audio")
    assert "disabled" in _rendered_row_value(output, "previous offsets")
    assert "false" in _rendered_row_value(output, "interactive alignment")
    assert "false" in _rendered_row_value(output, "force interactive")
    assert "tone mapping" in output
    assert "reference" in output
    assert "ffmpeg" in _rendered_row_value(output, "renderer")
    assert "disabled" in _rendered_row_value(output, "slow.pics")
    assert "public" in _rendered_row_value(output, "visibility")
    assert "auto-open=enabled" in _rendered_row_value(output, "report")
    assert "VSPreview" not in output


def test_run_plan_reports_auto_renderer_when_ffmpeg_is_not_forced(
    monkeypatch: MonkeyPatch,
) -> None:
    console = _console()
    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)

    print_at_a_glance(
        console,
        request=_request(),
        config=_config(),
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    renderer_row = _rendered_row_value(_render(console), "renderer")
    assert "auto (VapourSynth preferred)" in renderer_row


@pytest.mark.skipif(os.name == "nt", reason="Windows does not expose POSIX execute bits")
def test_at_a_glance_reports_non_executable_ffmpeg_override_as_unavailable(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    binary = tmp_path / "ffmpeg"
    binary.write_bytes(b"")
    binary.chmod(0o644)
    # Keep this test focused on the invalid FFmpeg override. The executable
    # environment-variable mapping is covered in tests/utils/test_subproc.py.
    monkeypatch.setenv("FRAME_COMPARE_FFPROBE_EXECUTABLE", sys.executable)
    monkeypatch.setenv("FRAME_COMPARE_FFMPEG_EXECUTABLE", str(binary.resolve()))
    console = _console()

    print_at_a_glance(
        console,
        request=_request(),
        config=_config(),
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    assert "false" in _rendered_row_value(_render(console), "FFmpeg audio")


def test_at_a_glance_prints_previous_offsets_effective_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)
    cases: tuple[
        tuple[Literal["disabled", "prompt", "always"], str],
        ...,
    ] = (
        ("disabled", "[SKIP] do not reuse previous offsets (disabled)"),
        ("prompt", "[WAIT] ask before reusing previous offsets (prompt)"),
        ("always", "[OK] reuse previous offsets when valid (always)"),
    )

    for mode, expected in cases:
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
        assert expected in previous_offsets_row


def test_at_a_glance_prints_effective_analysis_performance_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    config = _config()
    config.analysis.performance_mode = AnalysisPerformanceMode.PERFORMANCE
    console = _console()

    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)

    print_at_a_glance(
        console,
        request=_request(),
        config=config,
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    analysis_mode_row = _rendered_row_value(_render(console), "analysis mode")
    assert "performance" in analysis_mode_row


def test_at_a_glance_marks_analysis_mode_skipped_for_this_run(
    monkeypatch: MonkeyPatch,
) -> None:
    config = _config()
    config.analysis.performance_mode = AnalysisPerformanceMode.PERFORMANCE
    console = _console()
    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)

    print_at_a_glance(
        console,
        request=_request(skip_analysis=True),
        config=config,
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    analysis_mode_row = _rendered_row_value(_render(console), "analysis mode")
    assert "performance (skipped for this run)" in analysis_mode_row


def test_at_a_glance_preserves_literal_brackets_in_dynamic_paths(
    monkeypatch: MonkeyPatch,
) -> None:
    config = _config()
    config.paths.input_dir = Path("[bold]input[end]")
    config.paths.generated_dir = Path("[cyan]generated[end]")
    console = _console()

    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)

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
    assert "[cyan]generated[end]" in output


def test_at_a_glance_prints_vspreview_availability_when_probe_succeeds(
    monkeypatch: MonkeyPatch,
) -> None:
    from frame_compare.vspreview.adapter import VSPreviewAvailability, VSPreviewAvailabilityStatus

    config = _config()
    config.audio_alignment.use_vspreview = True
    console = _console()

    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)
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

    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)
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


def test_run_plan_preserves_all_material_settings(monkeypatch: MonkeyPatch) -> None:
    from frame_compare.vspreview.adapter import VSPreviewAvailability, VSPreviewAvailabilityStatus

    config = _config()
    config.analysis.user_frames = [12, 48]
    config.analysis.random_frame_count = 3
    config.analysis.dark_frame_count = 2
    config.analysis.bright_frame_count = 1
    config.analysis.motion_frame_count = 4
    config.analysis.random_seed = 99
    config.analysis.performance_mode = AnalysisPerformanceMode.PERFORMANCE
    config.analysis.ignore_lead_seconds = 2.5
    config.analysis.ignore_trail_seconds = 4.0
    config.sources.analysis_source = "fastest"
    config.screenshots.overlay_mode = OverlayMode.DIAGNOSTIC
    config.screenshots.geometry_mode = ScreenshotGeometryMode.ALIGNED
    config.screenshots.active_rect_detection = ScreenshotActiveRectDetection.AUTO
    config.audio_alignment.previous_offsets = "prompt"
    config.audio_alignment.use_vspreview = True
    config.report.auto_open = False
    config.slowpics.auto_upload = True
    config.slowpics.confirm_upload_after_report = True
    config.slowpics.visibility = Visibility.UNLISTED
    config.slowpics.copy_url_to_clipboard = False
    config.slowpics.open_in_browser = True
    config.slowpics.create_url_shortcut = False
    config.slowpics.webhook_url = "https://example.test/hook-secret"
    config.slowpics.delete_after_upload = True
    console = _console()

    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.AVAILABLE,
            message="available",
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
    assert "99" in _rendered_row_value(output, "seed")
    assert "performance" in _rendered_row_value(output, "analysis mode")
    assert "diagnostic" in _rendered_row_value(output, "overlay")
    assert "aligned" in _rendered_row_value(output, "geometry")
    assert "auto" in _rendered_row_value(output, "active-picture policy")
    assert "prompt" in _rendered_row_value(output, "previous offsets")
    assert "auto-open=disabled" in _rendered_row_value(output, "report")
    assert "unlisted" in _rendered_row_value(output, "visibility")
    for expected in (
        "Run plan",
        "Frame selection",
        "user=2, random=3, dark=2, bright=1, motion=4",
        "fastest",
        "lead=2.5s, trail=4s",
        "Rendering",
        "tone mapping",
        "previous offsets",
        "manual review",
        "report",
        "confirmation",
        "post-upload actions",
        "webhook=configured",
        "delete after upload",
    ):
        assert expected in output
    assert "https://example.test/hook-secret" not in output


@pytest.mark.parametrize("width", [60, 80])
def test_run_plan_no_color_uses_native_wrapping_without_truncation(
    monkeypatch: MonkeyPatch,
    width: int,
) -> None:
    config = _config()
    config.paths.input_dir = "/Volumes/external-media/very-long-source-directory"
    config.paths.generated_dir = "/Volumes/external-output/very-long-generated-directory"
    config.screenshots.overlay_mode = OverlayMode.DIAGNOSTIC
    console = _console_at_width(width)

    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)

    print_at_a_glance(
        console,
        request=_request(),
        config=config,
        root=_workspace_path("workspace-root"),
        config_path=_workspace_path("workspace-root", "config", "config.toml"),
    )

    output = _render(console)
    compact_output = "".join(output.replace("│", "").split())
    assert "Run plan" in output
    assert "diagnostic" in output
    assert "/Volumes/external-media/very-long-source-directory" in compact_output
    assert "/Volumes/external-output/very-long-generated-directory" in compact_output
    assert "..." not in output
    assert "…" not in output
    assert "[OK]" in output


def test_run_plan_wraps_complete_key_labels_at_very_narrow_width(
    monkeypatch: MonkeyPatch,
) -> None:
    console = _console_at_width(24)
    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)

    print_at_a_glance(
        console,
        request=_request(),
        config=_config(),
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    compact_output = "".join(_render(console).replace("│", "").split())
    assert "active-picturepolicy" in compact_output


def test_result_summary_uses_result_hierarchy_and_relative_paths() -> None:
    console = _console()
    root = _workspace_path()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            screenshot_dir=root / "generated" / "run-1" / "screenshots",
            report_path=root / "generated" / "run-1" / "report.html",
            slowpics_url="https://slow.pics/c/example",
            clips_processed=2,
            frame_count=12,
            duration_seconds=62.0,
            metrics_cache_status="hit",
            post_upload_actions=(
                PostUploadActionPresentationResult(
                    kind="shortcut",
                    success=True,
                    path=root / "generated" / "run-1" / "Example.url",
                ),
            ),
        ),
        quiet=False,
        root=root,
    )

    output = _render(console)
    assert "[OK] Comparison completed" in output
    assert "sources" in output
    assert "1m 02s" in output
    assert "Analysis cache" in output
    assert output.index("report.html") < output.index("screenshots")
    assert "Published" in output
    assert "Follow-up actions" in output
    relative_report = Path("generated") / "run-1" / "report.html"
    absolute_report = (root / relative_report).resolve()
    assert str(relative_report) in output
    assert str(absolute_report) not in output


def test_verbose_path_presentation_adds_absolute_detail_and_keeps_external_absolute(
    monkeypatch: MonkeyPatch,
) -> None:
    root = _workspace_path()
    plan_console = _console()
    config = _config()
    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)
    print_at_a_glance(
        plan_console,
        request=_request(),
        config=config,
        root=root,
        config_path=root / "config" / "config.toml",
        verbose=True,
    )

    plan_output = _render(plan_console)
    relative_config = Path("config") / "config.toml"
    absolute_config = (root / relative_config).resolve()
    assert str(relative_config) in plan_output
    assert f"(absolute: {absolute_config})" in plan_output

    normal_console = _console()
    external_report = (root.parent / "outside" / "report.html").resolve()
    print_result_summary(
        normal_console,
        result=RunResult(success=True, report_path=external_report),
        quiet=False,
        root=root,
    )
    normal_output = _render(normal_console)
    assert str(external_report) in normal_output

    verbose_console = _console()
    print_result_summary(
        verbose_console,
        result=RunResult(success=True, report_path=root / "generated" / "report.html"),
        quiet=False,
        root=root,
        verbose=True,
    )
    verbose_output = _render(verbose_console)
    relative_report = Path("generated") / "report.html"
    absolute_report = (root / relative_report).resolve()
    assert str(relative_report) in verbose_output
    assert f"(absolute: {absolute_report})" in verbose_output


def test_result_summary_warning_headline_cap_and_verbose_expansion() -> None:
    warnings = [f"warning {index}" for index in range(1, 11)]
    normal_console = _console()
    print_result_summary(
        normal_console,
        result=RunResult(success=True, warnings=warnings),
        quiet=False,
    )
    normal_output = _render(normal_console)
    assert "[WARN] Comparison completed with 10 warnings" in normal_output
    assert "warning 8" in normal_output
    assert "warning 9" not in normal_output
    assert "(2 more)" in normal_output

    verbose_console = _console()
    print_result_summary(
        verbose_console,
        result=RunResult(success=True, warnings=warnings),
        quiet=False,
        verbose=True,
    )
    verbose_output = _render(verbose_console)
    assert "[WARN] Comparison completed with 10 warnings" in verbose_output
    assert "warning 10" in verbose_output
    assert "(2 more)" not in verbose_output


def test_result_summary_does_not_duplicate_because_reason() -> None:
    console = _console()
    print_result_summary(
        console,
        result=RunResult(
            success=True,
            warnings=["slow.pics upload skipped because report confirmation was unavailable"],
        ),
        quiet=False,
    )

    output = _render(console)
    assert output.count("because report confirmation was unavailable") == 1
    assert "slow.pics upload skipped because report confirmation was unavailable" not in output


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
    assert "upload skipped by confirmation" in output
    assert "[SKIP] slow.pics" in output
    assert "✓" not in output


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
    assert "upload skipped because report confirmation was unavailable" in output
    assert "[SKIP] slow.pics" in output
    assert "✓" not in output


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
                warning="slow.pics clipboard: failed to copy URL",
            ),
        ),
    )

    output = _render(console)
    assert "alignment" in output
    assert "slow.pics" in output
    assert output.count("alignment") == 1
    assert "[WARN] align: encode_b low confidence; left unapplied and untrimmed" in output
    assert "[WARN] align: encode_c low confidence; left unapplied and untrimmed" in output
    assert "[SKIP] slow.pics upload skipped" in output
    assert output.count("because report confirmation was unavailable") == 1
    assert "action: clipboard" in output
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
    assert "[WARN] Comparison completed with 10 warnings" in output
    assert "Result" in output
    assert "status" in output
    assert "[OK] completed" in output
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
