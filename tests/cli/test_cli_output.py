from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

import pytest
from _pytest.monkeypatch import MonkeyPatch
from rich.console import Console

from frame_compare.cli.output import print_at_a_glance, print_result_summary
from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import AnalysisPerformanceMode, ConfigSchema
from frame_compare.config.schema_enums import (
    OverlayMode,
    ScreenshotActiveRectDetection,
    ScreenshotGeometryMode,
    Visibility,
)
from frame_compare.orchestration import RunRequest, RunResult
from frame_compare.utils.post_upload_actions import PostUploadActionResult


def _console() -> Console:
    return Console(record=True, no_color=True, width=200)


def _console_at_width(width: int) -> Console:
    return Console(record=True, no_color=True, width=width)


def _render(console: Console) -> str:
    return console.export_text(styles=False)


def _rendered_row_value(output: str, row_label: str) -> str:
    lines = output.splitlines()
    for index, line in enumerate(lines):
        content = line.partition("│")[2].partition("│")[0]
        row_prefix = f"   {row_label}"
        if not content.startswith(row_prefix):
            continue
        value_start = len(row_prefix)
        if value_start == len(content) or not content[value_start].isspace():
            continue
        if not content[value_start:].strip():
            continue
        rendered_lines = [line]
        for continuation in lines[index + 1 :]:
            continuation_content = continuation.partition("│")[2].partition("│")[0]
            if not continuation_content.strip():
                break
            if not continuation_content.startswith("   "):
                break
            if len(continuation_content) > 3 and not continuation_content[3].isspace():
                break
            rendered_lines.append(continuation)
        return "\n".join(rendered_lines)
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


def test_at_a_glance_prints_key_rows_without_vsview_probe(monkeypatch: MonkeyPatch) -> None:
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
    assert str(_workspace_path()) in output
    assert str(Path("config") / "config.toml") in _rendered_row_value(output, "config")
    assert "comparison_videos" in _rendered_row_value(output, "input")
    assert "generated" in _rendered_row_value(output, "output")
    with pytest.raises(AssertionError, match="run folders"):
        _rendered_row_value(output, "run folders")
    with pytest.raises(AssertionError, match="screenshots"):
        _rendered_row_value(output, "screenshots")
    assert "Frames" in output
    assert "10 random" in output
    assert "seed" in output
    assert "quality profile" in _rendered_row_value(output, "analysis")
    assert "FFmpeg audio" in _rendered_row_value(output, "tools")
    assert "do not reuse" in _rendered_row_value(output, "offsets")
    assert "HTML report" in output
    assert "BT.2390 reference" in _rendered_row_value(output, "tone map")
    assert "FFmpeg" in output
    assert "disabled by --no-upload" in output
    assert "opens when done" in output
    assert "VSView" not in output


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

    output = _render(console)
    assert "Rendering" in output
    assert "automatic" in output
    assert "VapourSynth preferred" in output


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

    assert "(unavailable)" in _rendered_row_value(_render(console), "tools")


def test_at_a_glance_skips_ffmpeg_audio_when_alignment_is_disabled(
    monkeypatch: MonkeyPatch,
) -> None:
    config = _config()
    config.audio_alignment.enable = False
    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)
    console = _console()

    print_at_a_glance(
        console,
        request=_request(),
        config=config,
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    output = _render(console)
    assert "Alignment" in output
    assert "disabled" in output
    tools_row = _rendered_row_value(output, "tools")
    assert "FFmpeg audio" in tools_row
    assert "(unavailable)" not in tools_row
    assert "not required" not in tools_row
    assert "VSView" not in tools_row


def test_at_a_glance_prints_previous_offsets_effective_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)
    cases: tuple[tuple[Literal["disabled", "prompt", "always"], str], ...] = (
        ("disabled", "do not reuse previous offsets"),
        ("prompt", "ask before reusing previous offsets"),
        ("always", "reuse previous offsets when valid"),
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
        previous_offsets_row = _rendered_row_value(output, "offsets")
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

    analysis_mode_row = _rendered_row_value(_render(console), "analysis")
    assert "performance profile" in analysis_mode_row


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

    analysis_mode_row = _rendered_row_value(_render(console), "analysis")
    assert "performance profile" in analysis_mode_row
    assert "skipped for this run" in analysis_mode_row


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


def test_at_a_glance_prints_vsview_availability_when_probe_succeeds(
    monkeypatch: MonkeyPatch,
) -> None:
    from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus

    config = _config()
    config.audio_alignment.use_vsview = True
    console = _console()

    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.check_vsview_availability",
        lambda: VSViewAvailability(
            status=VSViewAvailabilityStatus.AVAILABLE,
            message="VSView is available for interactive alignment",
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
    assert "audio, then VSView review" in output
    assert "VSView" in output
    tools_row = _rendered_row_value(output, "tools")
    assert "VSView" in tools_row
    vsview_part = tools_row.split("VSView", 1)[1]
    assert "(unavailable)" not in vsview_part
    assert "probe failed" not in vsview_part
    assert "✓ VSView" in tools_row
    assert "! FFmpeg audio (unavailable)" in tools_row


def test_at_a_glance_prints_vsview_probe_failure(monkeypatch: MonkeyPatch) -> None:
    from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus

    config = _config()
    config.audio_alignment.force_interactive = True
    console = _console()

    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.check_vsview_availability",
        lambda: VSViewAvailability(
            status=VSViewAvailabilityStatus.PROBE_FAILED,
            message="VSView availability probe failed",
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
    assert "audio, VSView required" in output
    assert "VSView" in output
    tools_row = _rendered_row_value(output, "tools")
    assert "probe failed (RuntimeError)" in tools_row
    assert "! VSView" in tools_row
    assert "display unavailable" not in output


def test_run_plan_preserves_all_material_settings(monkeypatch: MonkeyPatch) -> None:
    from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus

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
    config.audio_alignment.use_vsview = True
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
        "frame_compare.vsview.adapter.check_vsview_availability",
        lambda: VSViewAvailability(
            status=VSViewAvailabilityStatus.AVAILABLE,
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
    assert "performance profile" in _rendered_row_value(output, "analysis")
    assert "diagnostic" in _rendered_row_value(output, "overlay")
    assert "aligned geometry" in _rendered_row_value(output, "geometry")
    assert "active area automatic" in _rendered_row_value(output, "geometry")
    assert "2 user · 3 random · 2 dark · 1 bright · 4 motion" in _rendered_row_value(output, "mix")
    assert "fastest source" in _rendered_row_value(output, "analysis")
    assert "first 2.5 s · last 4.0 s" in _rendered_row_value(output, "skip")
    assert "ask before reusing previous offsets" in _rendered_row_value(output, "offsets")
    assert "HTML report" in output
    assert "opens when done" not in output
    assert "unlisted" in output
    assert "open browser" in _rendered_row_value(output, "after upload")
    assert "copy URL" not in _rendered_row_value(output, "after upload")
    assert "configured" in _rendered_row_value(output, "webhook")
    assert "delete uploaded screenshots when report-safe" in _rendered_row_value(output, "cleanup")
    assert "https://example.test/hook-secret" not in output


def test_run_plan_preserves_output_hierarchy(monkeypatch: MonkeyPatch) -> None:
    console = _console()
    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)

    print_at_a_glance(
        console,
        request=_request(),
        config=_config(),
        root=_workspace_path(),
        config_path=_workspace_path("config", "config.toml"),
    )

    output = _render(console)
    assert "Run plan" in output
    headings = ("Workspace", "Frames", "Rendering", "Alignment", "Review", "Publishing")
    heading_lines = {
        heading: next(
            index
            for index, line in enumerate(output.splitlines())
            if line.partition("│")[2].partition("│")[0].strip().startswith(heading)
        )
        for heading in headings
    }
    assert tuple(heading_lines.values()) == tuple(sorted(heading_lines.values()))

    def _row_line(key: str) -> int:
        return next(
            index
            for index, line in enumerate(output.splitlines())
            if line.partition("│")[2].partition("│")[0].strip().startswith(key)
        )

    assert _row_line("tools") < _row_line("offsets")
    assert _row_line("after upload") < _row_line("webhook") < _row_line("cleanup")


@pytest.mark.parametrize("width", [60, 80])
def test_run_plan_no_color_uses_native_wrapping_without_truncation(
    monkeypatch: MonkeyPatch,
    width: int,
) -> None:
    root = _workspace_path("workspace-root").resolve()
    input_dir = root.parent / "external-media" / "very-long-source-directory"
    generated_dir = root.parent / "external-output" / "very-long-generated-directory"
    config = _config()
    config.paths.input_dir = input_dir
    config.paths.generated_dir = generated_dir
    config.screenshots.overlay_mode = OverlayMode.DIAGNOSTIC
    console = _console_at_width(width)

    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)

    print_at_a_glance(
        console,
        request=_request(),
        config=config,
        root=root,
        config_path=root / "config" / "config.toml",
    )

    output = _render(console)
    compact_output = "".join(output.replace("│", "").split())
    assert "Run plan" in output
    assert "diagnostic" in output
    assert str(input_dir) in compact_output
    assert str(generated_dir) in compact_output
    assert "..." not in output
    assert "…" not in output
    assert "[OK]" not in output


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
    assert "afterupload" in compact_output


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
                PostUploadActionResult(
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
    assert "Comparison complete" in output
    assert "12 frames" in output
    assert "2 sources" in output
    assert "cache hit" in output
    assert output.index("report.html") < output.index("screenshots")
    assert "files" not in output
    assert "slow.pics" in output
    assert "shortcut" in output
    relative_report = Path("generated") / "run-1" / "report.html"
    absolute_report = (root / relative_report).resolve()
    assert str(relative_report) in output
    assert str(absolute_report) not in output


def test_result_summary_counts_screenshot_files_on_disk(tmp_path: Path) -> None:
    screenshots = tmp_path / "screenshots"
    screenshots.mkdir()
    for name in ("0-0.png", "0-1.png", "0-2.png"):
        (screenshots / name).write_bytes(b"\x89PNG\r\n\x1a\n")
    (screenshots / "notes.txt").write_text("not an image")

    console = _console()
    print_result_summary(
        console,
        result=RunResult(
            success=True,
            screenshot_dir=screenshots,
            frame_count=12,
            clips_processed=2,
        ),
        quiet=False,
    )

    assert "3 files" in _render(console)

    missing_console = _console()
    print_result_summary(
        missing_console,
        result=RunResult(
            success=True,
            screenshot_dir=screenshots / "absent",
            frame_count=12,
            clips_processed=2,
        ),
        quiet=False,
    )

    assert "files" not in _render(missing_console)


def test_result_summary_resolves_relative_artifact_link_against_root(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    root = tmp_path / "workspace"
    monkeypatch.chdir(tmp_path)
    console = _console()

    print_result_summary(
        console,
        result=RunResult(success=True, report_path=Path("generated") / "report.html"),
        quiet=False,
        root=root,
    )

    expected = (root / "generated" / "report.html").as_uri()
    assert f'href="{expected}"' in console.export_html()


def test_verbose_run_plan_path_presentation_adds_absolute_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    root = _workspace_path()
    config = _config()
    monkeypatch.setattr("frame_compare.utils.subproc.resolve_executable", _missing_executable)

    console = _console()
    print_at_a_glance(
        console,
        request=_request(),
        config=config,
        root=root,
        config_path=root / "config" / "config.toml",
        verbose=True,
    )

    output = _render(console)
    relative_config = Path("config") / "config.toml"
    absolute_config = (root / relative_config).resolve()
    assert str(relative_config) in output
    assert f"(absolute: {absolute_config})" in output


def test_result_summary_keeps_external_report_path_absolute() -> None:
    root = _workspace_path()
    console = _console()
    external_report = (root.parent / "outside" / "report.html").resolve()

    print_result_summary(
        console,
        result=RunResult(success=True, report_path=external_report),
        quiet=False,
        root=root,
    )

    output = _render(console)
    assert str(external_report) in output


def test_verbose_result_summary_path_presentation_adds_absolute_detail() -> None:
    root = _workspace_path()
    console = _console()

    print_result_summary(
        console,
        result=RunResult(success=True, report_path=root / "generated" / "report.html"),
        quiet=False,
        root=root,
        verbose=True,
    )
    output = _render(console)
    relative_report = Path("generated") / "report.html"
    absolute_report = (root / relative_report).resolve()
    assert str(relative_report) in output
    assert f"(absolute: {absolute_report})" in output


def test_result_summary_warning_headline_cap_and_verbose_expansion() -> None:
    warnings = [f"warning {index}" for index in range(1, 11)]
    normal_console = _console()
    print_result_summary(
        normal_console,
        result=RunResult(success=True, warnings=warnings),
        quiet=False,
    )
    normal_output = _render(normal_console)
    assert "Comparison complete · 10 warnings" in normal_output
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
    assert "Comparison complete · 10 warnings" in verbose_output
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
    assert "Comparison complete · 2 warnings" in output
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
    assert "not uploaded (declined)" in output
    assert "slow.pics" in output
    assert "[SKIP]" not in output


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
    assert "upload skipped" in output
    assert "report confirmation was unavailable" in output
    assert "slow.pics" in output
    assert "[SKIP]" not in output


def test_result_summary_shows_followup_failure_on_row_not_in_panel() -> None:
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
            PostUploadActionResult(
                kind="clipboard",
                success=False,
                warning="slow.pics clipboard: failed to copy URL",
            ),
        ),
    )

    output = _render(console)
    assert "Comparison complete · 4 warnings" in output
    assert "URL not copied" in output
    assert "action: clipboard" not in output
    assert "failed to copy URL" not in output
    assert "alignment" in output
    assert "slow.pics" in output
    assert output.count("alignment") == 1
    assert "! align: encode_b low confidence; left unapplied and untrimmed" in output
    assert "! align: encode_c low confidence; left unapplied and untrimmed" in output
    assert "– slow.pics upload skipped" in output
    assert output.count("because report confirmation was unavailable") == 1
    assert "[WARN]" not in output
    assert "[SKIP]" not in output
    assert output.index("encode_c") < output.index("slow.pics upload skipped")


def test_result_summary_uploaded_with_all_followups_succeeding() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            slowpics_url="https://slow.pics/c/example",
            report_path=_workspace_path("report.html"),
        ),
        quiet=False,
        post_upload_actions=(
            PostUploadActionResult(kind="clipboard", success=True),
            PostUploadActionResult(kind="browser", success=True),
            PostUploadActionResult(
                kind="shortcut",
                success=True,
                path=_workspace_path("Example.url"),
            ),
            PostUploadActionResult(kind="webhook", success=True),
        ),
    )

    output = _render(console)
    assert "Comparison complete" in output
    assert "warnings" not in output
    assert "Warnings" not in output
    assert "URL copied" in output
    assert "opened in browser" in output
    assert "shortcut" in output
    assert "delivered" in output


def test_result_summary_uploaded_with_each_followup_failing() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            slowpics_url="https://slow.pics/c/example",
        ),
        quiet=False,
        post_upload_actions=(
            PostUploadActionResult(
                kind="clipboard",
                success=False,
                warning="slow.pics clipboard: failed to copy URL",
            ),
            PostUploadActionResult(
                kind="browser",
                success=False,
                warning="slow.pics browser: failed to open URL: no browser accepted the request",
            ),
            PostUploadActionResult(
                kind="shortcut",
                success=False,
                warning="slow.pics shortcut: failed to write URL shortcut Example.url: boom",
            ),
            PostUploadActionResult(
                kind="webhook",
                success=False,
                warning="slow.pics webhook: delivery failed",
            ),
        ),
    )

    output = _render(console)
    assert "Comparison complete · 4 warnings" in output
    assert "URL not copied" in output
    assert "browser didn't open" in output
    assert "no browser accepted the request" in output
    assert "not created" in output
    assert "failed to write URL shortcut Example.url: boom" in output
    assert "delivery failed" in output
    assert "Warnings" not in output
    assert "failed to copy URL" not in output


def test_result_summary_uses_singular_warning_title() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(success=True, warnings=["metadata skipped"]),
        quiet=False,
    )

    output = _render(console)
    assert "Comparison complete · 1 warning" in output
    assert "Warnings" in output


def test_result_summary_upload_failure_shows_failed_title() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=False,
            warnings=["slow.pics upload failed: connection reset"],
        ),
        quiet=False,
    )

    output = _render(console)
    assert "Comparison failed" in output
    assert "slow.pics" in output


def test_result_summary_automatic_upload_without_confirmation() -> None:
    console = _console()

    print_result_summary(
        console,
        result=RunResult(
            success=True,
            slowpics_url="https://slow.pics/c/example",
        ),
        quiet=False,
    )

    output = _render(console)
    assert "Comparison complete" in output
    assert "https://slow.pics/c/example" in output
    assert "not uploaded" not in output
    assert "Warnings" not in output


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
    assert "1 frame" in output
    assert "2 sources" in output
    assert "cache skipped" in output
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
    assert "Comparison complete · 10 warnings" in output
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


def _timed_result() -> RunResult:
    return RunResult(
        success=True,
        duration_seconds=95.5,
        phase_timings={
            "preflight": 1.5,
            "load_sources": 2.5,
            "analyze": 10.0,
            "align": 60.0,
            "render": 20.0,
            "publish": 5.0,
            "confirm_slowpics_upload": 3.0,
        },
        vsview_review_seconds=42.5,
    )


def test_result_summary_time_rows_split_machine_and_user() -> None:
    console = _console()
    print_result_summary(console, result=_timed_result(), quiet=False)

    output = _render(console)
    assert "1m 35s total" in output
    assert "setup 4.0 s" in output
    assert "analyze 10.0 s" in output
    assert "align 17.5 s" in output
    assert "render 20.0 s" in output
    assert "upload 5.0 s" in output
    assert "VSView review 42.5 s" in output
    assert "prompts 3.0 s" in output


def test_result_summary_time_rows_omit_zero_components() -> None:
    console = _console()
    print_result_summary(
        console,
        result=RunResult(success=True, duration_seconds=5.0, phase_timings={"render": 5.0}),
        quiet=False,
    )

    output = _render(console)
    assert "5.0 s total" in output
    assert "render 5.0 s" in output
    assert "machine" in output
    assert "setup" not in output
    assert "analyze" not in output
    assert "align" not in output
    assert "upload" not in output
    assert "VSView review" not in output
    assert "prompts" not in output
    assert "you" not in output


def test_result_summary_time_rows_omitted_when_all_zero() -> None:
    console = _console()
    print_result_summary(
        console,
        result=RunResult(success=True, duration_seconds=2.0),
        quiet=False,
    )

    output = _render(console)
    assert "2.0 s total" in output
    assert "machine" not in output
    assert "you" not in output


def test_result_summary_time_rows_clamp_review_past_align() -> None:
    console = _console()
    print_result_summary(
        console,
        result=RunResult(
            success=True,
            duration_seconds=30.0,
            phase_timings={"align": 10.0},
            vsview_review_seconds=25.0,
        ),
        quiet=False,
    )

    output = _render(console)
    assert "align" not in output
    assert "VSView review 25.0 s" in output


def test_result_summary_time_rows_render_at_narrow_width() -> None:
    console = _console_at_width(80)
    print_result_summary(console, result=_timed_result(), quiet=False)

    output = _render(console)
    assert "1m 35s total" in output
    assert "setup 4.0 s" in output
    assert "align 17.5 s" in output
    assert "VSView review 42.5 s" in output
    assert "prompts 3.0 s" in output
