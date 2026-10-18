from __future__ import annotations

import asyncio
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from time import monotonic
from typing import cast

import pytest

from frame_compare.config.overrides import CLIConfigOverrides
from frame_compare.orchestration import phase_alignment
from frame_compare.orchestration.context import ClipState, RunContext
from frame_compare.services import alignment as alignment_service
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentOperationOutcome,
    AlignmentResult,
)
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import AlignmentClipIdentity, AlignmentClipRequest, AlignmentRequest
from frame_compare.vs.loader import VSLoader
from tests.alignment_review_test_support import (
    provisional_audio_attempt,
    unavailable_audio_attempt,
)
from tests.orchestration.phase_task_helpers import _clip, _context, _run_align_phase
from tests.render_test_support import paths_by_label
from tests.run_request_support import make_run_request
from tests.services.alignment_resolution_test_support import save_resolutions


def test_alignment_request_uses_untrimmed_probe_frame_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = _clip(ctx.reference.path, label="Reference", num_frames=321).with_trim(
        trim_start_frames=20,
        trim_end_frame_inclusive=99,
    )
    captured: list[AlignmentRequest] = []

    def fake_align(
        request: AlignmentRequest, *_args: object, **_kwargs: object
    ) -> AlignmentOperationOutcome:
        captured.append(request)
        return AlignmentOperationOutcome(
            (
                AlignmentResult(
                    reference_clip=request.reference.path.name,
                    comparison_clip=request.comparisons[0].path.name,
                    frame_offset=0,
                    time_offset_seconds=0.0,
                    correlation_score=1.0,
                    algorithm="cross_correlation",
                    source="computed",
                ),
            )
        )

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", fake_align)

    _run_align_phase(ctx, selected_frames=[0])

    assert captured[0].reference.source_frame_count == 321
    assert captured[0].workspace_root == ctx.workspace.root


@pytest.mark.parametrize("value", [0])
def test_alignment_request_requires_positive_integer_source_frame_count(
    tmp_path: Path, value: int | float | bool
) -> None:
    path = tmp_path / "source.mkv"

    with pytest.raises(ValueError, match="positive integer"):
        AlignmentClipRequest(
            path=path,
            label="Source",
            identity=AlignmentClipIdentity(path=path, size_bytes=0, mtime_ns=0),
            trim_start_frames=0,
            trim_end_frame_inclusive=None,
            effective_fps_num=24,
            effective_fps_den=1,
            source_fps_num=24,
            source_fps_den=1,
            source_frame_count=cast(int, value),
        )


def test_rejected_audio_attempt_survives_without_alignment_or_trim_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode")
    ctx = _context(tmp_path, comparisons=[comparison])
    attempt = unavailable_audio_attempt()

    monkeypatch.setattr(
        phase_alignment,
        "align_clips_from_request",
        lambda *_args, **_kwargs: AlignmentOperationOutcome(
            (
                AlignmentResult(
                    reference_clip=ctx.reference.path.name,
                    comparison_clip=comparison.path.name,
                    frame_offset=None,
                    time_offset_seconds=None,
                    correlation_score=0.0,
                    algorithm="cross_correlation",
                    source="computed",
                    applied=False,
                    diagnostic="no_single_offset",
                    audio_attempt=attempt,
                ),
            )
        ),
    )

    output = _run_align_phase(ctx, selected_frames=[0])

    assert output.comparisons[0].alignment is None
    assert output.reference.trim.trim_start_frames == 0
    assert output.comparisons[0].trim.trim_start_frames == 0
    assert output.comparisons[0].audio_attempt == attempt


def test_provisional_audio_candidate_cannot_reach_trim_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode")
    ctx = _context(tmp_path, comparisons=[comparison])
    attempt = provisional_audio_attempt(frame_offset=12)
    monkeypatch.setattr(
        phase_alignment,
        "align_clips_from_request",
        lambda *_args, **_kwargs: AlignmentOperationOutcome(
            (
                AlignmentResult(
                    reference_clip=ctx.reference.path.name,
                    comparison_clip=comparison.path.name,
                    frame_offset=None,
                    time_offset_seconds=None,
                    correlation_score=1.0,
                    algorithm="cross_correlation",
                    source="computed",
                    applied=False,
                    diagnostic="audio_only",
                    audio_attempt=attempt,
                ),
            )
        ),
    )
    real_calculate_trims = phase_alignment.calculate_alignment_trims

    def reject_authoritative_trim_input(
        ref_num_frames: int,
        comp_offsets: list[int | None],
        comp_num_frames: list[int],
    ) -> tuple[tuple[int, int], list[tuple[int, int]]]:
        if any(offset is not None for offset in comp_offsets):
            pytest.fail("provisional audio candidate reached authoritative trim input")
        return real_calculate_trims(ref_num_frames, comp_offsets, comp_num_frames)

    monkeypatch.setattr(
        phase_alignment, "calculate_alignment_trims", reject_authoritative_trim_input
    )
    monkeypatch.setattr(
        phase_alignment,
        "ClipAlignmentState",
        lambda **_kwargs: pytest.fail("provisional audio candidate reached alignment application"),
    )

    output = _run_align_phase(ctx, selected_frames=[0])

    assert output.comparisons[0].alignment is None
    assert output.reference.trim.trim_start_frames == 0
    assert output.comparisons[0].trim.trim_start_frames == 0
    assert output.comparisons[0].audio_attempt == attempt


def test_tampered_diagnostic_cannot_authorize_provisional_alignment_or_trims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode")
    ctx = _context(tmp_path, comparisons=[comparison])
    comparison.path.write_bytes(b"comparison")
    clips = []
    for clip in [ctx.reference, *ctx.comparisons]:
        stat = clip.path.stat()
        clips.append(
            replace(
                clip,
                probe=replace(
                    clip.probe,
                    fingerprint=replace(
                        clip.probe.fingerprint,
                        size_bytes=stat.st_size,
                        mtime_ns=stat.st_mtime_ns,
                    ),
                ),
            )
        )
    ctx.reference, *ctx.comparisons = clips
    ctx.workspace = replace(
        ctx.workspace,
        run_dir=ctx.workspace.generated_root / "run",
    )
    ctx.config = ctx.config.model_copy(
        update={
            "audio_alignment": ctx.config.audio_alignment.model_copy(update={"use_vsview": False})
        }
    )
    attempt = provisional_audio_attempt()
    provisional = AlignmentResult(
        reference_clip=ctx.reference.path.name,
        comparison_clip=comparison.path.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=1.0,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic="audio_only",
        audio_attempt=attempt,
    )
    monkeypatch.setattr(
        alignment_service,
        "_estimate_audio_pair",
        lambda *_args, **_kwargs: provisional,
    )

    real_align = alignment_service.align_clips_from_request

    async def align_then_tamper(
        request: AlignmentRequest,
        config: AlignmentConfig,
        *,
        progress: ProgressReporter | None = None,
        reference_fps: Fraction | None = None,
        frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
        verbose: bool = False,
        quiet: bool = False,
        json_output: bool = False,
        vs_loader: VSLoader | None = None,
    ) -> AlignmentOperationOutcome:
        outcome = await real_align(
            request,
            config,
            progress=progress,
            reference_fps=reference_fps,
            frame_props_by_stem=frame_props_by_stem,
            verbose=verbose,
            quiet=quiet,
            json_output=json_output,
            vs_loader=vs_loader,
        )
        results = outcome.results
        assert len(results) == 1
        assert results[0].applied is False
        assert results[0].frame_offset is None
        assert request.alignment_diagnostics_dir is not None
        diagnostic = request.alignment_diagnostics_dir / "comparison-1.json"
        assert diagnostic.is_file()
        diagnostic.write_text(
            '{"final_resolution":{"applied":true,"frame_offset":99}}\n',
            encoding="utf-8",
        )
        return outcome

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", align_then_tamper)

    output = _run_align_phase(ctx, selected_frames=[0])

    assert output.comparisons[0].alignment is None
    assert output.reference.trim.trim_start_frames == 0
    assert output.reference.trim.trim_end_frame_inclusive == 99
    assert output.comparisons[0].trim.trim_start_frames == 0
    assert output.comparisons[0].trim.trim_end_frame_inclusive == 99
    assert output.comparisons[0].audio_attempt == attempt


@pytest.mark.parametrize("changed_role", ["reference", "comparison"])
def test_primed_cache_source_drift_after_request_freezing_cannot_apply_trims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_role: str,
) -> None:
    from frame_compare.services.alignment_reuse_cache import (
        CACHE_FILE_NAME,
        comparison_cache_key,
        load_reusable_offset_entries,
    )
    from frame_compare.services.errors import AudioAlignmentError
    from frame_compare.services.types import ComparisonResolution
    from tests.alignment_review_test_support import frame_lag, trusted_audio_attempt

    comparison_path = tmp_path / "comparison_videos" / "encode.mkv"
    comparison_path.parent.mkdir(parents=True)
    comparison_path.write_bytes(b"comparison")
    ctx = _context(tmp_path, comparisons=[_clip(comparison_path, label="Encode")])
    ctx.config.audio_alignment.cache_results = True
    ctx.config.audio_alignment.use_vsview = False

    def prepared(clip: ClipState) -> ClipState:
        stat = clip.path.stat()
        return replace(
            clip,
            probe=replace(
                clip.probe,
                fingerprint=replace(
                    clip.probe.fingerprint,
                    size_bytes=stat.st_size,
                    mtime_ns=stat.st_mtime_ns,
                ),
            ),
        )

    ctx.reference = prepared(ctx.reference)
    ctx.comparisons = [prepared(ctx.comparisons[0])]
    frozen = phase_alignment._alignment_request_from_context(ctx)
    accepted = AlignmentResult(
        reference_clip=frozen.reference.path.name,
        comparison_clip=frozen.comparisons[0].path.name,
        frame_offset=3,
        time_offset_seconds=frame_lag(3) / 8000,
        correlation_score=1.0,
        algorithm="cross_correlation",
        source="computed",
        audio_attempt=trusted_audio_attempt(frame_offset=3),
        stability=trusted_audio_attempt(frame_offset=3).stability,
    )
    save_resolutions(
        frozen,
        [
            ComparisonResolution(
                result=accepted,
                comparison_cache_key=comparison_cache_key(frozen.comparisons[0]),
                origin="computed_this_run",
            )
        ],
    )
    assert load_reusable_offset_entries(frozen) is not None
    cache_file = frozen.shared_alignment_cache_dir / CACHE_FILE_NAME
    original_cache = cache_file.read_bytes()
    real_request_factory = phase_alignment._alignment_request_from_context

    def freeze_then_change(context: RunContext) -> AlignmentRequest:
        request = real_request_factory(context)
        changed = request.reference if changed_role == "reference" else request.comparisons[0]
        changed.path.write_bytes(b"changed source after request freezing")
        return request

    monkeypatch.setattr(phase_alignment, "_alignment_request_from_context", freeze_then_change)
    calculate_trims = pytest.fail
    monkeypatch.setattr(phase_alignment, "calculate_alignment_trims", calculate_trims)
    with pytest.raises(AudioAlignmentError, match="changed since preparation"):
        _run_align_phase(ctx, selected_frames=[0])
    assert ctx.reference.trim.trim_start_frames == 0
    assert ctx.comparisons[0].trim.trim_start_frames == 0
    assert ctx.comparisons[0].alignment is None
    assert cache_file.read_bytes() == original_cache


@pytest.mark.parametrize(
    "unavailable_kind", ["stream", "timeline", "ffmpeg_error", "ffmpeg_missing"]
)
@pytest.mark.parametrize("changed_role", ["reference", "comparison", None])
@pytest.mark.parametrize("cache_results", [False, True])
def test_optional_alignment_source_drift_stops_downstream_phases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_role: str | None,
    cache_results: bool,
    unavailable_kind: str,
) -> None:
    from frame_compare.orchestration.execution import (
        build_phases_after_align,
        build_phases_before_align,
    )
    from frame_compare.orchestration.execution_types import ExecutionState, MetadataPrefetch
    from frame_compare.orchestration.phases import PhaseStatus, execute_phases
    from frame_compare.services import alignment_audio
    from frame_compare.services.errors import AlignmentSourceIdentityError
    from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
    from frame_compare.utils.progress import NullProgressReporter
    from tests.orchestration.execute_run_helpers import FakeFFmpegRunner

    comparison_path = tmp_path / "comparison_videos" / "encode.mkv"
    comparison_path.parent.mkdir(parents=True)
    comparison_path.write_bytes(b"comparison")
    ctx = _context(tmp_path, comparisons=[_clip(comparison_path, label="Encode")])
    ctx.workspace = replace(ctx.workspace, run_dir=ctx.workspace.generated_root / "run")
    ctx.config.audio_alignment.cache_results = cache_results
    ctx.config.audio_alignment.use_vsview = False
    ctx.config.audio_alignment.reference_stream = 0
    ctx.config.audio_alignment.comparison_streams = {"encode": 0}

    def prepared(clip: ClipState) -> ClipState:
        stat = clip.path.stat()
        return replace(
            clip,
            probe=replace(
                clip.probe,
                fingerprint=replace(
                    clip.probe.fingerprint,
                    size_bytes=stat.st_size,
                    mtime_ns=stat.st_mtime_ns,
                ),
            ),
        )

    ctx.reference = prepared(ctx.reference)
    ctx.comparisons = [prepared(ctx.comparisons[0])]

    def unavailable_probe(_path: Path, **_kwargs: object) -> alignment_audio.ProbedStreams:
        if changed_role is not None:
            changed = ctx.reference if changed_role == "reference" else ctx.comparisons[0]
            changed.path.write_bytes(b"changed prepared source during unavailable audio probe")
        if unavailable_kind == "ffmpeg_error":
            raise FFmpegError("probe failed", returncode=1)
        if unavailable_kind == "ffmpeg_missing":
            raise FFmpegNotFoundError()
        stream = alignment_audio.AudioStreamInfo(
            audio_stream_index=0,
            absolute_stream_index=1,
            codec_name="pcm",
            channels=1,
            channel_layout="mono",
            sample_rate=8000,
            language=None,
            is_default=True,
            is_original=False,
            is_commentary=False,
            timeline=alignment_audio.AudioStreamTimeline(
                start_time=Fraction(0), duration=None, time_base=None, duration_basis="unavailable"
            ),
        )
        return alignment_audio.ProbedStreams(
            audio=() if unavailable_kind == "stream" else (stream,),
            video_start=alignment_audio.VideoStreamStart(
                start_time=Fraction(0), basis="default_zero"
            ),
        )

    monkeypatch.setattr(alignment_audio, "probe_streams", unavailable_probe)
    ctx.selection = replace(ctx.selection, frames=(0, 1, 2))
    state = ExecutionState()
    request = make_run_request(
        root=tmp_path,
        config=ctx.config,
        skip_metadata=True,
        overrides=CLIConfigOverrides(no_upload=True),
    )
    align = build_phases_before_align(
        request=request,
        config=ctx.config,
        monotonic_timer=monotonic,
        state=state,
        input_videos=[ctx.reference.path, comparison_path],
        workspace=ctx.workspace,
    )[2]
    downstream = build_phases_after_align(
        request=request,
        config=ctx.config,
        monotonic_timer=monotonic,
        ffmpeg_runner=FakeFFmpegRunner(),
        http_client=None,
        state=state,
        metadata_prefetch=MetadataPrefetch(metadata=None, was_attempted=False),
    )
    run = execute_phases([align, *downstream], ctx, NullProgressReporter())
    if changed_role is None:
        asyncio.run(run)
        assert align.status == (
            PhaseStatus.COMPLETED if unavailable_kind == "timeline" else PhaseStatus.WARNED
        ), state.warnings
        assert downstream[0].status == PhaseStatus.COMPLETED
        assert state.artifacts.render is not None
        assert paths_by_label(state.artifacts.render.clips)
        assert ctx.comparisons[0].alignment is None
        detail = {
            "stream": "audio stream override",
            "timeline": "selected_audio_timeline_unavailable",
            "ffmpeg_error": "FFmpeg failed with exit code 1",
            "ffmpeg_missing": "FFmpeg binary not found",
        }[unavailable_kind]
        assert any(detail in warning.text for warning in state.warnings)
    else:
        with pytest.raises(AlignmentSourceIdentityError, match="Start a fresh run") as caught:
            asyncio.run(run)
        assert caught.value.code == "FC-4005"
        assert caught.value.category == "source_identity_changed"
        assert align.status == PhaseStatus.FAILED
        assert all(phase.status == PhaseStatus.PENDING for phase in downstream)
        assert state.artifacts.render is None
        assert ctx.reference.trim.trim_start_frames == 0
        assert ctx.comparisons[0].trim.trim_start_frames == 0


@pytest.mark.parametrize(
    ("origins", "review_ran", "expected"),
    [
        (("computed_this_run", "computed_this_run"), False, "Alpha +0f · Beta +0f · audio"),
        (
            ("shared_computed_offsets", "shared_computed_offsets"),
            False,
            "Alpha +0f · Beta +0f · reused from last run",
        ),
        (
            ("shared_previous_offsets", "shared_previous_offsets"),
            False,
            "Alpha +0f · Beta +0f · previously confirmed",
        ),
        (
            ("preexisting_manual_override", "preexisting_manual_override"),
            False,
            "Alpha +0f · Beta +0f · manual offset",
        ),
        (
            ("interactive_confirmed_this_run", "interactive_confirmed_this_run"),
            True,
            "Alpha +0f · Beta +0f · confirmed in VSView",
        ),
        (
            ("interactive_confirmed_this_run", "computed_this_run"),
            True,
            "Alpha +0f confirmed in VSView · Beta +0f kept",
        ),
        (
            ("preexisting_manual_override", "computed_this_run"),
            False,
            "Alpha +0f manual offset · Beta +0f audio",
        ),
    ],
)
def test_final_alignment_summary_preserves_origins(
    tmp_path: Path, origins: tuple[str, str], review_ran: bool, expected: str
) -> None:
    from frame_compare.services.types import AlignmentWriteProvenance, ComparisonResolution
    from frame_compare.utils.progress import alignment_summary_lines
    from tests.services.alignment_request_test_support import alignment_request

    for name in ("ref.mkv", "a.mkv", "b.mkv"):
        (tmp_path / name).touch()
    request = alignment_request(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "a.mkv", tmp_path / "b.mkv"],
        generated_dir=tmp_path,
    )
    request = replace(
        request,
        comparisons=[
            replace(comp, short_name=name)
            for comp, name in zip(request.comparisons, ("Alpha", "Beta"), strict=True)
        ],
    )
    resolutions = tuple(
        ComparisonResolution(
            result=AlignmentResult(
                "ref.mkv",
                comp.path.name,
                0,
                0.0,
                1.0,
                None,
                "manual" if origin != "computed_this_run" else "computed",
            ),
            comparison_cache_key=comp.path.stem,
            origin=cast(AlignmentWriteProvenance, origin),
        )
        for comp, origin in zip(request.comparisons, origins, strict=True)
    )
    summary = phase_alignment._align_success_summary(
        request=request, resolutions=resolutions, review_ran=review_ran
    )
    assert alignment_summary_lines(summary, width=200)[0].plain == expected


@pytest.mark.parametrize(
    ("counts", "offset", "expected"),
    [
        ((240, 216), 0, "Reference has 1.0 s more at the end"),
        ((240, 216), 24, "Reference has 1.0 s more at the start"),
        ((240, 192), 24, "Reference has 1.0 s more at the start and 1.0 s more at the end"),
        ((240, 216, 264), 0, "Reference has 1.0 s more at the end, Beta has 2.0 s more at the end"),
        ((240, 240), 24, None),
    ],
)
def test_extra_footage_describes_final_shared_range(
    tmp_path: Path,
    counts: tuple[int, ...],
    offset: int,
    expected: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.services.types import ComparisonResolution

    comparisons = [
        _clip(tmp_path / f"comp{index}.mkv", label=name, num_frames=count)
        for index, (count, name) in enumerate(zip(counts[1:], ("Alpha", "Beta"), strict=False))
    ]
    ctx = _context(tmp_path, comparisons=comparisons)
    ctx.reference = _clip(ctx.reference.path, label="Reference", num_frames=counts[0])
    ctx.reference = replace(ctx.reference, label_is_explicit=True)
    ctx.comparisons = [replace(comp, label_is_explicit=True) for comp in ctx.comparisons]

    def align(
        request: AlignmentRequest, *_args: object, **_kwargs: object
    ) -> AlignmentOperationOutcome:
        results = tuple(
            AlignmentResult(
                request.reference.path.name,
                comp.path.name,
                offset,
                offset / 24,
                1.0,
                None,
                "computed",
            )
            for comp in request.comparisons
        )
        return AlignmentOperationOutcome(
            results,
            resolutions=tuple(
                ComparisonResolution(result, str(index), "computed_this_run")
                for index, result in enumerate(results)
            ),
            diagnostics_dir=tmp_path / "actual diagnostics",
        )

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", align)
    output = _run_align_phase(ctx, selected_frames=[30])
    assert output.alignment_summary is not None
    note = output.alignment_summary.extra_footage
    assert note == (
        expected + "; frames come from the range all sources share." if expected else None
    )
    from frame_compare.orchestration.coordinator import _assemble_run_result
    from frame_compare.orchestration.execution_types import ExecutionState
    from frame_compare.orchestration.phase_output_application import apply_phase_output

    state = ExecutionState()
    apply_phase_output(ctx=ctx, state=state, output=output)
    result = _assemble_run_result(
        artifacts=state.artifacts,
        selected_frames=output.selected_frames,
        context=ctx,
        preflight_warnings=[],
        phase_timings={},
        duration_seconds=1.0,
    )
    assert result.alignment_summary == output.alignment_summary
    assert result.alignment_diagnostics_dir == output.alignment_diagnostics_dir


@pytest.mark.parametrize("review_kind", ["none", "kept", "unresolved"])
def test_unapplied_and_unresolved_review_warn_only_the_align_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    review_kind: str,
) -> None:
    from io import StringIO

    from rich.console import Console
    from rich.text import Text

    from frame_compare.cli.output import print_result_summary
    from frame_compare.orchestration.coordinator import _assemble_run_result
    from frame_compare.orchestration.execution import _create_timed_phase
    from frame_compare.orchestration.execution_types import ExecutionState
    from frame_compare.orchestration.phases import PhaseStatus, execute_phases
    from frame_compare.services.alignment import format_rejected_alignment_warning
    from frame_compare.services.types import AlignmentReviewSummary, ComparisonResolution
    from frame_compare.utils.progress import RichProgressReporter, alignment_summary_lines
    from frame_compare.utils.progress_protocol import ProgressPhaseStatus

    comparison = _clip(tmp_path / "encode.mkv", label="Encode [red]", label_is_explicit=True)
    ctx = _context(tmp_path, comparisons=[comparison])
    unapplied = review_kind != "unresolved"
    original_result = AlignmentResult(
        ctx.reference.path.name,
        comparison.path.name,
        None if unapplied else 0,
        None if unapplied else 0.0,
        0.0,
        None,
        "computed",
        applied=not unapplied,
        diagnostic="no_single_offset" if unapplied else None,
    )
    resolution = ComparisonResolution(original_result, "key", "computed_this_run")
    outcome = AlignmentOperationOutcome(
        (original_result,),
        AlignmentReviewSummary(
            review_ran=review_kind == "kept",
            comparisons_kept=int(review_kind == "kept"),
            review_unresolved=review_kind == "unresolved",
        ),
        resolutions=(resolution,),
    )
    monkeypatch.setattr(
        phase_alignment, "align_clips_from_request", lambda *_args, **_kwargs: outcome
    )
    output = _run_align_phase(ctx, selected_frames=[0])
    assert output.has_unapplied_offsets is unapplied
    assert output.review_unresolved is (review_kind == "unresolved")
    expected_warnings = (
        [format_rejected_alignment_warning(original_result, comparison_label=comparison.label)]
        if unapplied
        else []
    )
    assert output.warnings == expected_warnings
    if unapplied:
        assert output.comparisons[0].alignment is None
    else:
        assert output.comparisons[0].alignment is not None
    assert output.reference.trim.trim_start_frames == ctx.reference.trim.trim_start_frames
    assert output.reference.effective_num_frames() == ctx.reference.effective_num_frames()
    assert output.comparisons[0].trim.trim_start_frames == comparison.trim.trim_start_frames
    assert output.comparisons[0].effective_num_frames() == comparison.effective_num_frames()
    assert output.alignment_summary is not None
    expected_value = (
        "not applied (kept)"
        if review_kind == "kept"
        else "not applied"
        if unapplied
        else "+0f · audio"
    )
    inline = alignment_summary_lines(output.alignment_summary, width=200)
    assert inline[0].plain == "Encode [red] " + expected_value
    rows = alignment_summary_lines(output.alignment_summary, width=10)
    assert rows[1].plain == "Encode [red]  " + ("+0f" if not unapplied else expected_value)

    stream = StringIO()
    console = Console(file=stream, no_color=True, width=120)
    monkeypatch.setattr("frame_compare.utils.progress.human_console", lambda **_kwargs: console)
    reporter = RichProgressReporter(no_color=True)
    state = ExecutionState()
    phase = _create_timed_phase(
        "align",
        "align",
        None,
        lambda _ctx: output,
        state,
        lambda: 0.0,
        state.phase_timings,
        state.warnings,
    )
    asyncio.run(execute_phases([phase], ctx, reporter))
    assert phase.status == PhaseStatus.COMPLETED
    assert phase.success_status == ProgressPhaseStatus.WARNED
    phase_line = next(
        line for line in Text.from_ansi(stream.getvalue()).plain.splitlines() if "! Align" in line
    )
    assert " · " in phase_line
    assert state.warnings == expected_warnings
    result = _assemble_run_result(
        artifacts=state.artifacts,
        selected_frames=[0],
        context=ctx,
        preflight_warnings=[],
        phase_timings={},
        duration_seconds=0,
    )
    completion = StringIO()
    print_result_summary(
        Console(file=completion, no_color=True, width=120), result=result, quiet=False
    )
    baseline = StringIO()
    print_result_summary(
        Console(file=baseline, no_color=True, width=120),
        result=replace(result, alignment_summary=None),
        quiet=False,
    )
    assert completion.getvalue().splitlines()[1] == baseline.getvalue().splitlines()[1]
    assert "Encode [red] " + expected_value in completion.getvalue()
