from __future__ import annotations

import asyncio
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from time import monotonic
from typing import cast

import pytest

from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.loader import load_config
from frame_compare.orchestration import phase_alignment
from frame_compare.orchestration.context import ClipState, RunContext
from frame_compare.services import alignment as alignment_service
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentResult,
    AlignmentReviewSummary,
)
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import AlignmentClipIdentity, AlignmentClipRequest, AlignmentRequest
from frame_compare.vs.loader import VSLoader
from tests.alignment_review_test_support import (
    provisional_audio_attempt,
    unavailable_audio_attempt,
)
from tests.orchestration.phase_task_helpers import _clip, _run_align_phase, _workspace

# U3 keeps only the C1 config surface; the shared helper config still lists the
# removed C2 estimator keys, so this file builds its context from valid TOML.
_VALID_MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[analysis]
random_frame_count = 3
random_seed = 7

[audio_alignment]
enable = true
max_offset_seconds = 4.5
use_vsview = true
force_interactive = false
cache_results = false
channel_strategy = "best_channel"
reference_stream = 1
comparison_streams = { encode = 2 }

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


def _context(tmp_path: Path, *, comparisons: list[ClipState] | None = None) -> RunContext:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(_VALID_MINIMAL_CONFIG, encoding="utf-8")
    config = load_config(config_path)
    reference_path = tmp_path / "comparison_videos" / "reference.mkv"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_bytes(b"reference")
    reference = _clip(reference_path, label="Reference")
    return RunContext(
        config=config,
        workspace=_workspace(tmp_path),
        reference=reference,
        comparisons=[] if comparisons is None else comparisons,
        analysis_selection_domain="test-selection-domain",
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
        analysis_clip=reference,
    )


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
    ) -> list[AlignmentResult]:
        captured.append(request)
        return [
            AlignmentResult(
                reference_clip=request.reference.path.name,
                comparison_clip=request.comparisons[0].path.name,
                frame_offset=0,
                time_offset_seconds=0.0,
                correlation_score=1.0,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", fake_align)

    _run_align_phase(ctx, selected_frames=[0])

    assert captured[0].reference.source_frame_count == 321


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
        lambda *_args, **_kwargs: [
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
            )
        ],
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
        lambda *_args, **_kwargs: [
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
            )
        ],
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
        review_summary: AlignmentReviewSummary | None = None,
        vs_loader: VSLoader | None = None,
    ) -> list[AlignmentResult]:
        results = await real_align(
            request,
            config,
            progress=progress,
            reference_fps=reference_fps,
            frame_props_by_stem=frame_props_by_stem,
            verbose=verbose,
            quiet=quiet,
            json_output=json_output,
            review_summary=review_summary,
            vs_loader=vs_loader,
        )
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
        return results

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
        save_reusable_offsets,
    )
    from frame_compare.services.errors import AudioAlignmentError
    from frame_compare.services.types import AlignmentProvenance
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
    save_reusable_offsets(
        frozen,
        [
            AlignmentProvenance(
                result=accepted,
                comparison_cache_key=comparison_cache_key(frozen.comparisons[0]),
                provenance="computed_this_run",
                evidence_availability="current_attempt",
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
    from frame_compare.orchestration.types import RunRequest
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
        # Drift while the real service is planning an unavailable audio attempt.
        # No applied result or cache authority will trigger an acceptance check.
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
    state = ExecutionState(selected_frames=[0, 1, 2])
    request = RunRequest(root=tmp_path, skip_metadata=True, no_upload=True)
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
        assert state.artifacts.render.screenshots_by_label
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
