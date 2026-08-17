"""Metadata, report, publish, confirmation, and cleanup phase output contracts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from frame_compare.analysis.types import (
    SelectionBreakdown,
    SelectionDetail,
)
from frame_compare.orchestration import phase_post_render
from frame_compare.orchestration.execution import build_phases_after_align
from frame_compare.orchestration.execution_types import (
    ExecutionState,
    MetadataPrefetch,
    PublishPhaseOutput,
    RenderArtifacts,
    ReportPhaseOutput,
    RunArtifacts,
)
from frame_compare.orchestration.phases import execute_phases
from frame_compare.orchestration.types import (
    RunRequest,
    SlowpicsUploadConfirmationDecision,
    SlowpicsUploadConfirmationRequest,
)
from frame_compare.render.types import RenderedClipFacts
from frame_compare.services.errors import SlowpicsError
from frame_compare.services.publishers import PublishResult
from frame_compare.services.slowpics_post_upload import (
    SlowpicsPostUploadRequest,
)
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from frame_compare.utils.post_upload_actions import PostUploadActionResult
from frame_compare.utils.progress import NullProgressReporter
from tests.orchestration.phase_task_helpers import (
    _clip,
    _context,
    _RenderRunner,
)


def _render_artifacts(
    *,
    screenshots_by_label: dict[str, list[Path]],
    screenshot_dir: Path | None,
    source_frames_by_label: dict[str, list[int]] | None = None,
) -> RenderArtifacts:
    geometry = RenderedGeometryFacts(
        source_size=(1920, 1080),
        active_picture=ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True),
        cropped_size=(1920, 1080),
        scaled_size=(1920, 1080),
        final_canvas_size=(1920, 1080),
        is_noop=True,
    )
    frames = source_frames_by_label or {
        label: list(range(len(paths))) for label, paths in screenshots_by_label.items()
    }
    return RenderArtifacts(
        screenshots_by_label=screenshots_by_label,
        frame_facts_by_label={
            label: [RenderedFrameFacts(source_frame=frame, picture_type="I") for frame in values]
            for label, values in frames.items()
        },
        clip_facts_by_label={
            label: RenderedClipFacts(
                size_bytes=0,
                source_resolution=(1920, 1080),
                source_total_frames=100,
                signal=SourceSignalFacts(is_hdr=False),
                presentation_state=PresentationState.SDR,
                tonemap_settings=None,
                geometry=geometry,
            )
            for label in screenshots_by_label
        },
        screenshot_dir=screenshot_dir,
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

    monkeypatch.setattr(phase_post_render, "resolve_run_metadata", _fake_resolve_run_metadata)

    async with httpx.AsyncClient() as client:
        output = await phase_post_render.run_metadata_phase(
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
    render = _render_artifacts(
        screenshots_by_label={
            "Reference": [tmp_path / "screenshots" / "reference_1.png"],
            "Encode 1": [tmp_path / "screenshots" / "encode_1.png"],
        },
        screenshot_dir=tmp_path / "screenshots",
        source_frames_by_label={"Reference": [5], "Encode 1": [5]},
    )
    artifacts = RunArtifacts(
        render=render,
        slowpics_url="https://slow.pics/c/example",
    )
    captured: dict[str, Any] = {}
    expected_path = tmp_path / "run" / "report.html"

    def _fake_generate_report(
        report_data: object, report_config: object, *, output_path: Path
    ) -> Path:
        captured["report_data"] = report_data
        captured["report_config"] = report_config
        captured["output_path"] = output_path
        return expected_path

    monkeypatch.setattr(phase_post_render, "generate_report", _fake_generate_report)

    output = phase_post_render.run_report_phase(
        ctx,
        frames=[5],
        render=artifacts.render,
        metadata=artifacts.resolved_metadata,
        slowpics_url=artifacts.slowpics_url,
    )

    report_data = captured["report_data"]
    assert output.report_path == expected_path
    assert captured["output_path"] == expected_path
    assert artifacts.report_path is None
    assert report_data.frames == [5]
    assert report_data.frame_details == []
    assert [image.path for image in report_data.clips[0].images] == render.screenshots_by_label[
        "Reference"
    ]
    assert [image.path for image in report_data.clips[1].images] == render.screenshots_by_label[
        "Encode 1"
    ]
    assert report_data.slowpics_url == "https://slow.pics/c/example"
    assert [(clip.name, clip.resolution, clip.fps) for clip in report_data.clips] == [
        ("Reference", (1920, 1080), 24.0),
        ("Encode 1", (1920, 1080), 24.0),
    ]
    assert captured["report_config"] == ctx.config.report


def test_run_report_phase_requires_reserved_run_folder(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.workspace = replace(ctx.workspace, run_dir=None)
    render = _render_artifacts(
        screenshots_by_label={
            "Reference": [tmp_path / "screenshots" / "reference_1.png"],
        },
        screenshot_dir=tmp_path / "screenshots",
        source_frames_by_label={"Reference": [1]},
    )

    with pytest.raises(RuntimeError, match="reserved run folder"):
        phase_post_render.run_report_phase(
            ctx,
            frames=[1],
            render=render,
            metadata=None,
            slowpics_url=None,
        )


def test_run_report_phase_builds_four_clip_payload_inputs_in_clip_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "encode_a.mkv", label="Encode 1")
    comp_b = _clip(tmp_path / "comparison_videos" / "encode_b.mkv", label="Encode 2")
    comp_c = _clip(tmp_path / "comparison_videos" / "encode_c.mkv", label="Encode 3")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b, comp_c])
    screenshots_by_label = {
        "Reference": [tmp_path / "screenshots" / "reference_1.png"],
        "Encode 1": [tmp_path / "screenshots" / "encode_a_1.png"],
        "Encode 2": [tmp_path / "screenshots" / "encode_b_1.png"],
        "Encode 3": [tmp_path / "screenshots" / "encode_c_1.png"],
    }
    render = _render_artifacts(
        screenshots_by_label=screenshots_by_label,
        screenshot_dir=tmp_path / "screenshots",
        source_frames_by_label={label: [12] for label in screenshots_by_label},
    )
    captured: dict[str, Any] = {}

    def _fake_generate_report(
        report_data: object, report_config: object, *, output_path: Path
    ) -> Path:
        captured["report_data"] = report_data
        captured["report_config"] = report_config
        captured["output_path"] = output_path
        return output_path

    monkeypatch.setattr(phase_post_render, "generate_report", _fake_generate_report)

    phase_post_render.run_report_phase(
        ctx,
        frames=[12],
        render=render,
        metadata=None,
        slowpics_url=None,
    )

    report_data = captured["report_data"]
    assert captured["output_path"] == tmp_path / "run" / "report.html"
    assert [clip.name for clip in report_data.clips] == [
        "Reference",
        "Encode 1",
        "Encode 2",
        "Encode 3",
    ]
    assert [[image.path for image in clip.images] for clip in report_data.clips] == [
        screenshots_by_label["Reference"],
        screenshots_by_label["Encode 1"],
        screenshots_by_label["Encode 2"],
        screenshots_by_label["Encode 3"],
    ]
    assert report_data.frames == [12]


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
    render = _render_artifacts(
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
        source_frames_by_label={"Reference": [4, 5], "Encode 1": [1, 2]},
    )
    captured: dict[str, Any] = {}
    expected_path = tmp_path / "run" / "report.html"

    def _fake_generate_report(
        report_data: object, report_config: object, *, output_path: Path
    ) -> Path:
        captured["report_data"] = report_data
        captured["report_config"] = report_config
        captured["output_path"] = output_path
        return expected_path

    monkeypatch.setattr(phase_post_render, "generate_report", _fake_generate_report)

    output = phase_post_render.run_report_phase(
        ctx,
        frames=[1, 2],
        render=render,
        metadata=None,
        slowpics_url=None,
    )

    report_data = captured["report_data"]
    assert output.report_path == expected_path
    assert captured["output_path"] == expected_path
    assert report_data.frames == [1, 2]
    assert [
        (detail.label, detail.detail, detail.category) for detail in report_data.frame_details
    ] == [
        ("User", "Selected comparison frame", "user_override"),
        ("Frame 2", "Selected comparison frame", "quantile_bright"),
    ]
    assert captured["report_config"] == ctx.config.report


async def test_run_publish_phase_sets_url_from_publish_result_and_delegates_post_upload_actions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode-final-source.mkv", label="Encode 1")
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
    render = _render_artifacts(
        screenshots_by_label={
            "Reference": [ref_10, ref_20],
            "Encode 1": [enc_10, enc_20],
        },
        screenshot_dir=screenshot_dir,
    )
    captured: dict[str, Any] = {}
    captured_post_upload_request: SlowpicsPostUploadRequest | None = None

    async def _fake_publish_to_slowpics(**kwargs: object) -> PublishResult:
        captured.update(kwargs)
        upload_plan = cast(Any, kwargs["upload_plan"])
        return PublishResult(
            url="https://slow.pics/c/collateral",
            screenshot_count=len(upload_plan.file_paths),
            upload_duration_seconds=0.1,
            uploaded_file_paths=tuple(upload_plan.file_paths),
        )

    async def _fake_run_slowpics_post_upload_actions(
        request: SlowpicsPostUploadRequest,
    ) -> tuple[PostUploadActionResult, ...]:
        nonlocal captured_post_upload_request
        captured_post_upload_request = request
        return (
            PostUploadActionResult(
                kind="shortcut",
                success=True,
                path=tmp_path / "Collateral.url",
                message="slow.pics URL shortcut written",
            ),
        )

    monkeypatch.setattr(phase_post_render, "publish_to_slowpics", _fake_publish_to_slowpics)
    monkeypatch.setattr(
        phase_post_render,
        "run_slowpics_post_upload_actions",
        _fake_run_slowpics_post_upload_actions,
    )

    async with httpx.AsyncClient() as client:
        output = await phase_post_render.run_publish_phase(
            ctx,
            client=client,
            metadata=metadata,
            render=render,
            selected_frames=[10, 20],
        )
        assert captured["client"] is client

    assert captured["config"] == ctx.config.slowpics
    assert captured["collection_metadata"].title == "Collateral (2004)"
    assert captured["collection_metadata"].tmdb_id == 3
    assert captured["collection_metadata"].tmdb_media_type == "movie"
    upload_plan = captured["upload_plan"]
    assert upload_plan.file_paths == [ref_10, enc_10, ref_20, enc_20]
    assert output.slowpics_url == "https://slow.pics/c/collateral"
    assert output.uploaded_file_paths == (ref_10, enc_10, ref_20, enc_20)
    assert captured_post_upload_request is not None
    assert captured_post_upload_request.workspace == ctx.workspace
    assert captured_post_upload_request.config is ctx.config.slowpics
    assert captured_post_upload_request.slowpics_url == "https://slow.pics/c/collateral"
    assert captured_post_upload_request.collection_title == "Collateral (2004)"
    assert output.post_upload_actions == (
        PostUploadActionResult(
            kind="shortcut",
            success=True,
            path=tmp_path / "Collateral.url",
            message="slow.pics URL shortcut written",
        ),
    )


async def test_run_publish_phase_rejects_duplicate_clip_labels_at_translation_seam(
    tmp_path: Path,
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Reference")
    ctx = _context(tmp_path, comparisons=[comparison])
    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()
    screenshot = screenshot_dir / "10 - reference.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\n")
    render = _render_artifacts(
        screenshots_by_label={"Reference": [screenshot]},
        screenshot_dir=screenshot_dir,
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(SlowpicsError, match="Duplicate clip label in slow.pics upload input"):
            await phase_post_render.run_publish_phase(
                ctx,
                client=client,
                metadata=None,
                render=render,
                selected_frames=[10],
            )


async def test_run_publish_phase_skips_shortcut_when_config_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.create_url_shortcut = False
    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()
    screenshot = screenshot_dir / "10 - reference.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\n")
    render = _render_artifacts(
        screenshots_by_label={"Reference": [screenshot]},
        screenshot_dir=screenshot_dir,
    )

    async def _fake_publish_to_slowpics(**kwargs: object) -> PublishResult:
        upload_plan = cast(Any, kwargs["upload_plan"])
        return PublishResult(
            url="https://slow.pics/c/example",
            screenshot_count=len(upload_plan.file_paths),
            upload_duration_seconds=0.1,
            uploaded_file_paths=tuple(upload_plan.file_paths),
        )

    async def _no_post_upload_actions(
        _request: SlowpicsPostUploadRequest,
    ) -> tuple[PostUploadActionResult, ...]:
        return ()

    monkeypatch.setattr(phase_post_render, "publish_to_slowpics", _fake_publish_to_slowpics)
    monkeypatch.setattr(
        phase_post_render,
        "run_slowpics_post_upload_actions",
        _no_post_upload_actions,
    )

    async with httpx.AsyncClient() as client:
        output = await phase_post_render.run_publish_phase(
            ctx,
            client=client,
            metadata=None,
            render=render,
            selected_frames=[10],
        )

    assert output.slowpics_url == "https://slow.pics/c/example"
    assert output.uploaded_file_paths == (screenshot,)
    assert output.post_upload_actions == ()


async def test_report_confirmed_decline_skips_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.auto_upload = True
    ctx.config.slowpics.confirm_upload_after_report = True
    ctx.config.report.enable = True
    report_path = tmp_path / "report.html"
    state = ExecutionState(
        artifacts=RunArtifacts(report_path=report_path, report_succeeded=True),
        selected_frames=[10],
    )
    callback_calls: list[SlowpicsUploadConfirmationRequest] = []

    def _decline(
        request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision:
        callback_calls.append(request)
        return "declined"

    async def _unexpected_publish(*_args: object, **_kwargs: object) -> PublishPhaseOutput:
        raise AssertionError("declined report-confirmed upload must not publish")

    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_publish_phase",
        _unexpected_publish,
    )

    async with httpx.AsyncClient() as client:
        phases = build_phases_after_align(
            request=RunRequest(root=tmp_path),
            monotonic_timer=lambda: 0.0,
            ffmpeg_runner=cast(Any, _RenderRunner()),
            http_client=client,
            state=state,
            metadata_prefetch=MetadataPrefetch(None, False),
            config=ctx.config,
            confirm_slowpics_upload=_decline,
        )
        selected_phases = [
            phase for phase in phases if phase.name in {"confirm_slowpics_upload", "publish"}
        ]
        await execute_phases(selected_phases, ctx, NullProgressReporter())

    assert callback_calls == [SlowpicsUploadConfirmationRequest(report_path=report_path)]
    assert state.artifacts.slowpics_upload_confirmation_status == "declined"
    assert state.artifacts.slowpics_url is None
    assert state.artifacts.uploaded_slowpics_file_paths == ()


async def test_report_confirmed_available_report_confirms_then_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.auto_upload = True
    ctx.config.slowpics.confirm_upload_after_report = True
    ctx.config.report.enable = True
    report_path = tmp_path / "report.html"
    state = ExecutionState(
        artifacts=RunArtifacts(report_path=report_path, report_succeeded=True),
        selected_frames=[10],
    )
    publish_calls = 0

    def _confirm(
        request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision:
        del request
        return "confirmed"

    async def _fake_publish(*_args: object, **_kwargs: object) -> PublishPhaseOutput:
        nonlocal publish_calls
        publish_calls += 1
        return PublishPhaseOutput(slowpics_url="https://slow.pics/c/confirmed")

    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_publish_phase",
        _fake_publish,
    )

    async with httpx.AsyncClient() as client:
        phases = build_phases_after_align(
            request=RunRequest(root=tmp_path),
            monotonic_timer=lambda: 0.0,
            ffmpeg_runner=cast(Any, _RenderRunner()),
            http_client=client,
            state=state,
            metadata_prefetch=MetadataPrefetch(None, False),
            config=ctx.config,
            confirm_slowpics_upload=_confirm,
        )
        selected_phases = [
            phase for phase in phases if phase.name in {"confirm_slowpics_upload", "publish"}
        ]
        await execute_phases(selected_phases, ctx, NullProgressReporter())

    assert publish_calls == 1
    assert state.artifacts.slowpics_upload_confirmation_status == "confirmed"
    assert state.artifacts.slowpics_url == "https://slow.pics/c/confirmed"


async def test_report_confirmed_report_failure_skips_prompt_and_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.auto_upload = True
    ctx.config.slowpics.confirm_upload_after_report = True
    ctx.config.report.enable = True
    state = ExecutionState(artifacts=RunArtifacts(), selected_frames=[10])

    def _failing_report(*_args: object, **_kwargs: object) -> ReportPhaseOutput:
        raise RuntimeError("report failed")

    def _unexpected_confirm(
        request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision:
        del request
        raise AssertionError("unavailable report must not prompt")

    async def _unexpected_publish(*_args: object, **_kwargs: object) -> PublishPhaseOutput:
        raise AssertionError("unavailable report must not publish")

    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_report_phase",
        _failing_report,
    )
    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_publish_phase",
        _unexpected_publish,
    )

    async with httpx.AsyncClient() as client:
        phases = build_phases_after_align(
            request=RunRequest(root=tmp_path),
            monotonic_timer=lambda: 0.0,
            ffmpeg_runner=cast(Any, _RenderRunner()),
            http_client=client,
            state=state,
            metadata_prefetch=MetadataPrefetch(None, False),
            config=ctx.config,
            confirm_slowpics_upload=_unexpected_confirm,
        )
        selected_phases = [
            phase
            for phase in phases
            if phase.name in {"report", "confirm_slowpics_upload", "publish"}
        ]
        await execute_phases(selected_phases, ctx, NullProgressReporter())

    assert state.artifacts.slowpics_upload_confirmation_status == "report_unavailable"
    assert state.artifacts.slowpics_url is None
    assert state.warnings == [
        "report: report failed",
        "slow.pics upload skipped because report confirmation was unavailable",
    ]


async def test_report_confirmed_report_payload_uses_no_slowpics_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.config.slowpics.auto_upload = True
    ctx.config.slowpics.confirm_upload_after_report = True
    ctx.config.report.enable = True
    state = ExecutionState(
        artifacts=RunArtifacts(slowpics_url="https://slow.pics/c/stale"),
        selected_frames=[10],
    )
    captured_slowpics_url: str | None = "not-captured"

    def _capture_report(*_args: object, **kwargs: object) -> ReportPhaseOutput:
        nonlocal captured_slowpics_url
        captured_slowpics_url = cast(str | None, kwargs["slowpics_url"])
        return ReportPhaseOutput(report_path=tmp_path / "report.html", report_succeeded=True)

    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_report_phase",
        _capture_report,
    )

    phases = build_phases_after_align(
        request=RunRequest(root=tmp_path),
        monotonic_timer=lambda: 0.0,
        ffmpeg_runner=cast(Any, _RenderRunner()),
        http_client=None,
        state=state,
        metadata_prefetch=MetadataPrefetch(None, False),
        config=ctx.config,
    )
    report_phase = next(phase for phase in phases if phase.name == "report")
    await execute_phases([report_phase], ctx, NullProgressReporter())

    assert captured_slowpics_url is None
    assert state.artifacts.report_path == tmp_path / "report.html"


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

    output = phase_post_render.run_post_report_cleanup_phase(
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
    shortcut = tmp_path / "Collateral.url"
    for path in (*uploaded, stale):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
    shortcut.write_text("[InternetShortcut]\nURL=https://slow.pics/c/example\n", encoding="utf-8")

    output = phase_post_render.run_post_report_cleanup_phase(
        ctx,
        uploaded_file_paths=uploaded,
        report_succeeded=True,
    )

    assert output.warnings == []
    assert not any(path.exists() for path in uploaded)
    assert stale.exists()
    assert shortcut.exists()


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

    output = phase_post_render.run_post_report_cleanup_phase(
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

    output = phase_post_render.run_post_report_cleanup_phase(
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

    output = phase_post_render.run_post_report_cleanup_phase(
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
    warning_events: list[str] = []

    def _raise_permission_error(self: Path) -> None:
        if self == uploaded[0]:
            raise PermissionError("locked")
        Path.unlink(self)

    def _capture_warning(event: str, **kwargs: object) -> None:
        del kwargs
        warning_events.append(event)

    monkeypatch.setattr(Path, "unlink", _raise_permission_error)
    monkeypatch.setattr(phase_post_render.log, "warning", _capture_warning)

    output = phase_post_render.run_post_report_cleanup_phase(
        ctx,
        uploaded_file_paths=uploaded,
        report_succeeded=False,
    )

    assert output.warnings == [
        f"cleanup: failed to delete uploaded screenshot {uploaded[0]}: locked"
    ]
    assert warning_events == ["slowpics_uploaded_file_delete_failed"]


async def test_warn_only_publish_phase_keeps_sanitized_service_error_in_warning_and_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.slowpics.auto_upload = True
    sanitized_error = SlowpicsError("Image upload failed with status 400")
    warning_events: list[str] = []

    async def _fake_run_publish_phase(*_args: object, **_kwargs: object) -> object:
        raise sanitized_error

    def _capture_warning(event: str, **kwargs: object) -> None:
        del kwargs
        warning_events.append(event)

    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_publish_phase",
        _fake_run_publish_phase,
    )
    monkeypatch.setattr("frame_compare.orchestration.phases.log.warning", _capture_warning)

    state = ExecutionState(
        artifacts=RunArtifacts(
            render=_render_artifacts(
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
            monotonic_timer=lambda: 0.0,
            ffmpeg_runner=cast(Any, _RenderRunner()),
            http_client=client,
            state=state,
            metadata_prefetch=MetadataPrefetch(None, False),
            config=ctx.config,
        )
        publish_phase = next(phase for phase in phases if phase.name == "publish")

        await execute_phases([publish_phase], ctx, NullProgressReporter())

    assert len(state.warnings) == 1
    assert "publish:" in state.warnings[0]
    assert "Image upload failed with status 400" in state.warnings[0]
    assert warning_events == ["phase_warned"]
