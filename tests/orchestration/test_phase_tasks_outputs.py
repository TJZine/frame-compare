"""Direct tests for orchestration phase task behavior."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from frame_compare.analysis.types import (
    SelectionBreakdown,
    SelectionDetail,
)
from frame_compare.config.schema import OverlayMode
from frame_compare.orchestration import phase_tasks
from frame_compare.orchestration.execution import build_phases_after_align
from frame_compare.orchestration.phases import execute_phases
from frame_compare.orchestration.types import (
    ExecutionState,
    MetadataPrefetch,
    RenderArtifacts,
    RunArtifacts,
    RunRequest,
)
from frame_compare.services.errors import SlowpicsError
from frame_compare.services.publishers import PublishResult
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.progress import NullProgressReporter
from frame_compare.vs.types import HDRMetadata
from tests.orchestration.phase_task_helpers import (
    _clip,
    _context,
    _RenderRunner,
)


async def test_run_metadata_phase_resolves_when_enabled_and_client_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    expected = TmdbMetadata(
        tmdb_id=2,
        title="Thief",
        original_title="Thief",
        year=1981,
        media_type="movie",
    )
    captured: dict[str, Any] = {}

    async def _fake_resolve_run_metadata(**kwargs: object) -> TmdbMetadata:
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(phase_tasks, "resolve_run_metadata", _fake_resolve_run_metadata)

    async with httpx.AsyncClient() as client:
        output = await phase_tasks.run_metadata_phase(
            ctx,
            client=client,
            metadata_prefetch=MetadataPrefetch(None, False),
        )
        assert captured["client"] is client

    assert captured["filenames"] == ["reference.mkv"]
    assert captured["config"] == ctx.config
    assert output.resolved_metadata == expected


def test_run_report_phase_builds_report_data_and_records_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    render = RenderArtifacts(
        screenshots_by_label={
            "Reference": [tmp_path / "screenshots" / "reference_1.png"],
            "Encode 1": [tmp_path / "screenshots" / "encode_1.png"],
        },
        screenshot_dir=tmp_path / "screenshots",
    )
    artifacts = RunArtifacts(
        render=render,
        slowpics_url="https://slow.pics/c/example",
    )
    captured: dict[str, Any] = {}
    expected_path = tmp_path / "report.html"

    def _fake_generate_report(report_data: object, report_config: object) -> Path:
        captured["report_data"] = report_data
        captured["report_config"] = report_config
        return expected_path

    monkeypatch.setattr(phase_tasks, "generate_report", _fake_generate_report)

    output = phase_tasks.run_report_phase(
        ctx,
        frames=[5],
        render=artifacts.render,
        metadata=artifacts.resolved_metadata,
        slowpics_url=artifacts.slowpics_url,
    )

    report_data = captured["report_data"]
    assert output.report_path == expected_path
    assert artifacts.report_path is None
    assert report_data.frames == [5]
    assert report_data.frame_details == []
    assert report_data.clips[0].screenshots == render.screenshots_by_label["Reference"]
    assert report_data.clips[1].screenshots == render.screenshots_by_label["Encode 1"]
    assert report_data.slowpics_url == "https://slow.pics/c/example"
    assert [(clip.name, clip.resolution, clip.fps) for clip in report_data.clips] == [
        ("Reference", (1920, 1080), 24.0),
        ("Encode 1", (1920, 1080), 24.0),
    ]
    assert captured["report_config"] == ctx.config.report


def test_run_report_phase_passes_reference_source_frame_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=20)
    ctx.selection_breakdown = SelectionBreakdown(quantile_bright=[5])
    ctx.selection_details_by_source_frame = {
        4: SelectionDetail(
            frame_index=4,
            label="User",
            source="analysis",
            timecode="00:00:00.167",
            score=0.5,
            clip_role="analyze",
            notes="user_override",
        )
    }
    render = RenderArtifacts(
        screenshots_by_label={
            "Reference": [
                tmp_path / "screenshots" / "reference_1.png",
                tmp_path / "screenshots" / "reference_2.png",
            ],
            "Encode 1": [
                tmp_path / "screenshots" / "encode_1.png",
                tmp_path / "screenshots" / "encode_2.png",
            ],
        },
        screenshot_dir=tmp_path / "screenshots",
    )
    captured: dict[str, Any] = {}
    expected_path = tmp_path / "report.html"

    def _fake_generate_report(report_data: object, report_config: object) -> Path:
        captured["report_data"] = report_data
        captured["report_config"] = report_config
        return expected_path

    monkeypatch.setattr(phase_tasks, "generate_report", _fake_generate_report)

    output = phase_tasks.run_report_phase(
        ctx,
        frames=[1, 2],
        render=render,
        metadata=None,
        slowpics_url=None,
    )

    report_data = captured["report_data"]
    assert output.report_path == expected_path
    assert report_data.frames == [1, 2]
    assert [(detail.label, detail.detail, detail.category) for detail in report_data.frame_details] == [
        ("User", "Source frame 4 (00:00:00.167)", "user_override"),
        ("Bright", "Source frame 5", "quantile_bright"),
    ]
    assert captured["report_config"] == ctx.config.report


def test_run_render_phase_maps_aligned_frames_to_source_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=20)
    ctx.comparisons = [comparison.with_trim(trim_start_frames=1, trim_end_frame_inclusive=18)]
    ctx.selection_breakdown = SelectionBreakdown(quantile_dark=[4])
    captured: dict[str, Any] = {}

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        captured.update(kwargs)
        options = kwargs["options"]
        assert options.warnings is not None
        options.warnings.append("render: geometry alignment skipped")
        return {"Reference": [tmp_path / "reference.png"]}

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )

    runner = cast(Any, _RenderRunner())
    output = phase_tasks.run_render_phase(
        ctx,
        frames=[1],
        runner=runner,
    )

    requests = captured["batch_requests"]
    assert requests[0].source_frames == [4]
    assert requests[0].display_frames == [1]
    assert requests[0].selection_labels == ["Dark"]
    assert requests[1].source_frames == [2]
    assert captured["output_dir"] == ctx.workspace.screenshots_dir
    options = captured["options"]
    assert options.overlay_mode == ctx.config.screenshots.overlay_mode
    assert options.ffmpeg_runner is runner
    assert options.reporter is ctx.reporter
    assert output.render == RenderArtifacts(
        screenshots_by_label={"Reference": [tmp_path / "reference.png"]},
        screenshot_dir=ctx.workspace.screenshots_dir,
        warnings=["render: geometry alignment skipped"],
    )


def test_run_render_phase_prefers_typed_selection_details_in_reference_source_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.screenshots.overlay_mode = OverlayMode.DIAGNOSTIC
    ctx.config.diagnostics.per_frame_nits = True
    ctx.config.color.target_nits = 200
    ctx.reference = replace(
        ctx.reference,
        probe=replace(
            ctx.reference.probe,
            is_hdr=True,
            hdr_metadata=HDRMetadata(
                mastering_display="G(0.265,0.690)B(0.150,0.060)R(0.680,0.320)WP(0.3127,0.3290)L(1000.0,0.0050)",
                max_cll=1000,
                max_fall=400,
                color_primaries=9,
                transfer=16,
                matrix=9,
            ),
            preserved_frame_props={
                "DolbyVisionRPU": 1,
                "_Range": 0,
                "DolbyVision_L1_Average": 12.5,
                "DolbyVision_L1_Maximum": 450.0,
                "DolbyVision_L6_MaxCLL": 900.0,
                "DolbyVision_L6_MaxFALL": 300.0,
            },
        ),
    )
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=20)
    ctx.comparisons = [
        replace(
            comparison.with_trim(trim_start_frames=1, trim_end_frame_inclusive=18),
            probe=replace(
                comparison.probe,
                is_hdr=True,
                hdr_metadata=HDRMetadata(
                    mastering_display=None,
                    max_cll=600,
                    max_fall=200,
                    color_primaries=9,
                    transfer=16,
                    matrix=9,
                ),
                preserved_frame_props={"_ColorRange": 0},
            ),
        )
    ]
    ctx.selection_breakdown = SelectionBreakdown(quantile_dark=[4])
    ctx.selection_details_by_source_frame = {
        4: SelectionDetail(
            frame_index=4,
            label="User",
            source="analysis",
            timecode="00:00:00.167",
            score=0.5,
            clip_role="analyze",
            notes="user_override",
        )
    }
    captured: dict[str, Any] = {}

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        captured.update(kwargs)
        return {"Reference": [tmp_path / "reference.png"]}

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )

    runner = cast(Any, _RenderRunner())
    phase_tasks.run_render_phase(
        ctx,
        frames=[1],
        runner=runner,
    )

    requests = captured["batch_requests"]
    assert requests[0].selection_labels == ["User"]
    assert requests[0].selection_details is not None
    assert requests[0].selection_details[0] is not None
    assert requests[0].selection_details[0].label == "User"
    assert requests[0].diagnostic_metadata is not None
    assert requests[0].diagnostic_metadata[0] is not None
    assert requests[0].diagnostic_metadata[0].max_cll == 1000
    assert requests[0].diagnostic_metadata[0].color_range == "limited"
    assert requests[0].diagnostic_metadata[0].dolby_vision is not None
    assert requests[0].diagnostic_metadata[0].measurement is not None
    assert requests[0].diagnostic_metadata[0].measurement.avg_nits == pytest.approx(100.0)
    assert requests[1].selection_details is not None
    assert requests[1].selection_details[0] is not None
    assert requests[1].selection_details[0].frame_index == 4
    assert requests[1].diagnostic_metadata is not None
    assert requests[1].diagnostic_metadata[0] is not None
    assert requests[1].diagnostic_metadata[0].max_cll == 600
    assert requests[1].diagnostic_metadata[0].color_range == "full"


def test_run_render_phase_uses_alignment_reselected_source_domain_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1", num_frames=220
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=60, trim_end_frame_inclusive=219)
    ctx.comparisons = [comparison.with_trim(trim_start_frames=0, trim_end_frame_inclusive=159)]
    ctx.selection_breakdown = SelectionBreakdown(quantile_dark=[60], quantile_bright=[219])
    ctx.selection_details_by_source_frame = {
        60: SelectionDetail(
            frame_index=60,
            label="Dark",
            source="analysis",
            timecode="00:00:02.500",
            clip_role="analyze",
            notes="quantile_dark",
        ),
        219: SelectionDetail(
            frame_index=219,
            label="Bright",
            source="analysis",
            timecode="00:00:09.125",
            clip_role="analyze",
            notes="quantile_bright",
        ),
    }
    captured: dict[str, Any] = {}

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        captured.update(kwargs)
        return {"Reference": [tmp_path / "reference.png"]}

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )

    phase_tasks.run_render_phase(
        ctx,
        frames=[0, 159],
        runner=cast(Any, _RenderRunner()),
    )

    requests = captured["batch_requests"]
    assert requests[0].selection_labels == ["Dark", "Bright"]
    assert requests[0].selection_details is not None
    assert [
        detail.label if detail is not None else None for detail in requests[0].selection_details
    ] == [
        "Dark",
        "Bright",
    ]


def test_run_report_phase_without_screenshots_clears_existing_report_path(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    artifacts = RunArtifacts(report_path=tmp_path / "stale.html")

    output = phase_tasks.run_report_phase(
        ctx,
        frames=[1],
        render=artifacts.render,
        metadata=artifacts.resolved_metadata,
        slowpics_url=artifacts.slowpics_url,
    )

    assert output.report_path is None
    assert artifacts.report_path == tmp_path / "stale.html"


async def test_run_publish_phase_sets_url_from_publish_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode-final-source.mkv", label="Encode 1"
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    metadata = TmdbMetadata(
        tmdb_id=3,
        title="Collateral",
        original_title="Collateral",
        year=2004,
        media_type="movie",
    )
    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()
    ref_10 = screenshot_dir / "10 - reference.png"
    enc_10 = screenshot_dir / "10 - encode.png"
    ref_20 = screenshot_dir / "20 - reference.png"
    enc_20 = screenshot_dir / "20 - encode.png"
    stale = screenshot_dir / "stale.png"
    for screenshot in (ref_10, enc_10, ref_20, enc_20, stale):
        screenshot.write_bytes(b"\x89PNG\r\n\x1a\n")
    render = RenderArtifacts(
        screenshots_by_label={
            "Reference": [ref_10, ref_20],
            "Encode 1": [enc_10, enc_20],
        },
        screenshot_dir=screenshot_dir,
    )
    captured: dict[str, Any] = {}
    captured_clip_names: list[tuple[str, str]] = []
    real_build_slowpics_upload_plan = phase_tasks.build_slowpics_upload_plan

    def _capturing_build_slowpics_upload_plan(**kwargs: object) -> object:
        clips = kwargs["clips"]
        captured_clip_names.extend((clip.label, clip.image_name) for clip in clips)
        return real_build_slowpics_upload_plan(
            selected_frames=cast(list[int], kwargs["selected_frames"]),
            clips=cast(Any, clips),
            screenshots_by_label=cast(dict[str, list[Path]], kwargs["screenshots_by_label"]),
        )

    async def _fake_publish_to_slowpics(**kwargs: object) -> PublishResult:
        captured.update(kwargs)
        upload_plan = cast(Any, kwargs["upload_plan"])
        return PublishResult(
            url="https://slow.pics/c/collateral",
            screenshot_count=len(upload_plan.file_paths),
            upload_duration_seconds=0.1,
            uploaded_file_paths=tuple(upload_plan.file_paths),
        )

    monkeypatch.setattr(
        phase_tasks, "build_slowpics_upload_plan", _capturing_build_slowpics_upload_plan
    )
    monkeypatch.setattr(phase_tasks, "publish_to_slowpics", _fake_publish_to_slowpics)

    async with httpx.AsyncClient() as client:
        output = await phase_tasks.run_publish_phase(
            ctx,
            client=client,
            metadata=metadata,
            render=render,
            selected_frames=[10, 20],
        )
        assert captured["client"] is client

    assert captured["screenshot_dir"] == screenshot_dir
    assert captured["config"] == ctx.config.slowpics
    assert captured["metadata"] == metadata
    upload_plan = captured["upload_plan"]
    assert upload_plan.file_paths == [ref_10, enc_10, ref_20, enc_20]
    assert [row.row_name for row in upload_plan.rows] == ["10", "20"]
    assert [image.image_name for image in upload_plan.rows[0].images] == [
        "reference",
        "encode-final-source",
    ]
    assert captured_clip_names == [
        ("Reference", "reference"),
        ("Encode 1", "encode-final-source"),
    ]
    assert output.slowpics_url == "https://slow.pics/c/collateral"
    assert output.uploaded_file_paths == (ref_10, enc_10, ref_20, enc_20)


async def test_run_publish_phase_rejects_duplicate_clip_labels_at_translation_seam(
    tmp_path: Path,
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Reference")
    ctx = _context(tmp_path, comparisons=[comparison])
    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()
    screenshot = screenshot_dir / "10 - reference.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\n")
    render = RenderArtifacts(
        screenshots_by_label={"Reference": [screenshot]},
        screenshot_dir=screenshot_dir,
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(SlowpicsError, match="Duplicate clip label in slow.pics upload input"):
            await phase_tasks.run_publish_phase(
                ctx,
                client=client,
                metadata=None,
                render=render,
                selected_frames=[10],
            )


def test_post_report_cleanup_skips_non_embedded_reports(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.delete_after_upload = True
    ctx.config.report.enable = True
    ctx.config.report.embed_images = False
    uploaded = (
        tmp_path / "screenshots" / "planned-a.png",
        tmp_path / "screenshots" / "planned-b.png",
    )
    stale = tmp_path / "screenshots" / "stale.png"
    for path in (*uploaded, stale):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\n")

    output = phase_tasks.run_post_report_cleanup_phase(
        ctx,
        uploaded_file_paths=uploaded,
        report_succeeded=True,
    )

    assert output.warnings == []
    assert all(path.exists() for path in uploaded)
    assert stale.exists()


def test_post_report_cleanup_deletes_planned_files_after_embedded_report_success(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.delete_after_upload = True
    ctx.config.report.enable = True
    ctx.config.report.embed_images = True
    uploaded = (
        tmp_path / "screenshots" / "planned-a.png",
        tmp_path / "screenshots" / "planned-b.png",
    )
    stale = tmp_path / "screenshots" / "stale.png"
    for path in (*uploaded, stale):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\n")

    output = phase_tasks.run_post_report_cleanup_phase(
        ctx,
        uploaded_file_paths=uploaded,
        report_succeeded=True,
    )

    assert output.warnings == []
    assert not any(path.exists() for path in uploaded)
    assert stale.exists()


def test_post_report_cleanup_deletes_planned_files_when_reports_disabled(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.delete_after_upload = True
    ctx.config.report.enable = False
    ctx.config.report.embed_images = False
    uploaded = (tmp_path / "screenshots" / "planned.png",)
    stale = tmp_path / "screenshots" / "stale.png"
    for path in (*uploaded, stale):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\n")

    output = phase_tasks.run_post_report_cleanup_phase(
        ctx,
        uploaded_file_paths=uploaded,
        report_succeeded=False,
    )

    assert output.warnings == []
    assert not uploaded[0].exists()
    assert stale.exists()


def test_post_report_cleanup_skips_without_upload_handoff(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.delete_after_upload = True
    ctx.config.report.enable = False
    stale = tmp_path / "screenshots" / "stale.png"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(b"\x89PNG\r\n\x1a\n")

    output = phase_tasks.run_post_report_cleanup_phase(
        ctx,
        uploaded_file_paths=(),
        report_succeeded=False,
    )

    assert output.warnings == []
    assert stale.exists()


def test_post_report_cleanup_requires_report_success_when_report_enabled(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.delete_after_upload = True
    ctx.config.report.enable = True
    ctx.config.report.embed_images = True
    uploaded = (tmp_path / "screenshots" / "planned.png",)
    uploaded[0].parent.mkdir(parents=True, exist_ok=True)
    uploaded[0].write_bytes(b"\x89PNG\r\n\x1a\n")

    output = phase_tasks.run_post_report_cleanup_phase(
        ctx,
        uploaded_file_paths=uploaded,
        report_succeeded=False,
    )

    assert output.warnings == []
    assert uploaded[0].exists()


def test_post_report_cleanup_returns_warning_and_logs_for_delete_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.delete_after_upload = True
    ctx.config.report.enable = False
    uploaded = (tmp_path / "screenshots" / "planned.png",)
    uploaded[0].parent.mkdir(parents=True, exist_ok=True)
    uploaded[0].write_bytes(b"\x89PNG\r\n\x1a\n")
    warning_calls: list[tuple[str, dict[str, object]]] = []

    def _raise_permission_error(self: Path) -> None:
        if self == uploaded[0]:
            raise PermissionError("locked")
        Path.unlink(self)

    def _capture_warning(event: str, **kwargs: object) -> None:
        warning_calls.append((event, kwargs))

    monkeypatch.setattr(Path, "unlink", _raise_permission_error)
    monkeypatch.setattr(phase_tasks.log, "warning", _capture_warning)

    output = phase_tasks.run_post_report_cleanup_phase(
        ctx,
        uploaded_file_paths=uploaded,
        report_succeeded=False,
    )

    assert output.warnings == [
        f"cleanup: failed to delete uploaded screenshot {uploaded[0]}: locked"
    ]
    assert warning_calls == [
        (
            "slowpics_uploaded_file_delete_failed",
            {"path": str(uploaded[0]), "error": "locked"},
        )
    ]


async def test_warn_only_publish_phase_keeps_sanitized_service_error_in_warning_and_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.slowpics.auto_upload = True
    sanitized_error = SlowpicsError("Image upload failed with status 400")
    warning_calls: list[tuple[str, dict[str, object]]] = []

    async def _fake_run_publish_phase(*_args: object, **_kwargs: object) -> object:
        raise sanitized_error

    def _capture_warning(event: str, **kwargs: object) -> None:
        warning_calls.append((event, kwargs))

    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_publish_phase",
        _fake_run_publish_phase,
    )
    monkeypatch.setattr("frame_compare.orchestration.phases.log.warning", _capture_warning)

    state = ExecutionState(
        artifacts=RunArtifacts(
            render=RenderArtifacts(
                screenshots_by_label={
                    "Reference": [tmp_path / "screenshots" / "reference.png"],
                    "Encode 1": [tmp_path / "screenshots" / "encode.png"],
                },
                screenshot_dir=tmp_path / "screenshots",
            )
        ),
        selected_frames=[10],
    )
    async with httpx.AsyncClient() as client:
        phases = build_phases_after_align(
            request=RunRequest(root=tmp_path),
            clock=lambda: datetime(2026, 5, 31, tzinfo=UTC),
            ffmpeg_runner=cast(Any, _RenderRunner()),
            http_client=client,
            state=state,
            metadata_prefetch=MetadataPrefetch(None, False),
        )
        publish_phase = next(phase for phase in phases if phase.name == "publish")

        await execute_phases([publish_phase], ctx, NullProgressReporter())

    assert len(state.warnings) == 1
    assert "publish:" in state.warnings[0]
    assert "Image upload failed with status 400" in state.warnings[0]
    assert warning_calls == [
        (
            "phase_warned",
            {
                "phase": "publish",
                "error_type": "SlowpicsError",
                "error": str(sanitized_error),
                "exc_info": sanitized_error,
            },
        )
    ]
