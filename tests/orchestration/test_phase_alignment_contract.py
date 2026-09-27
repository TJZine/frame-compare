from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.loader import load_config
from frame_compare.orchestration import phase_alignment
from frame_compare.orchestration.context import ClipState, RunContext
from frame_compare.services import alignment as alignment_service
from frame_compare.services.alignment_decision import ALIGNMENT_ESTIMATOR_POLICY
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentResult,
    AlignmentReviewSummary,
)
from frame_compare.utils.alignment_evidence import (
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioChunkColumns,
    AudioChunkRun,
    AudioDecisionCandidate,
    AudioStageOutcome,
    SelectedAudioStreamEvidence,
    VideoCheckObservation,
)
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import AlignmentClipIdentity, AlignmentClipRequest, AlignmentRequest
from tests.orchestration.phase_task_helpers import _clip, _run_align_phase, _workspace

_REFERENCE_DIGEST = "a" * 64
_COMPARISON_DIGEST = "b" * 64
_DIAGNOSTIC_POLICY = "retained-audio-evidence-v1"
_FPS_NUM = 24
_FPS_DEN = 1
_CHUNK_SAMPLES = 40000
_LAG_SAMPLES = 240000
_MAX_OFFSET_SECONDS = 30.0
_AGREE_PSR = 30.0

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


def _frame_lag(frame_offset: int) -> int:
    """Return the exact 8 kHz lag for the whole-frame offsets used by fixtures."""
    lag = frame_offset * 8000 // _FPS_NUM
    assert lag * _FPS_NUM == frame_offset * 8000
    return lag


def _subframe_estimate(lag: int) -> float:
    return lag / 8000 * (_FPS_NUM / _FPS_DEN)


def _stream(role: str, digest: str) -> SelectedAudioStreamEvidence:
    return SelectedAudioStreamEvidence(
        role="reference" if role == "reference" else "comparison",  # type: ignore[arg-type]
        source_identity_digest=digest,
        audio_stream_index=0,
        absolute_stream_index=1,
        selection_method="automatic_metadata",
        selection_rank=(0, 0, 0, 0),
        codec_name="aac",
        sample_rate=48000,
        channels=2,
        channel_layout="stereo",
        language="eng",
        is_default=True,
        is_original=False,
        is_commentary=False,
        language_match="not_applicable" if role == "reference" else "match",
        commentary_match="not_applicable" if role == "reference" else "match",
        stream_start_num=0,
        stream_start_den=1,
        stream_start_basis="metadata",
        input_start_num=0,
        input_start_den=1,
        input_start_basis="metadata",
        time_base_num=1,
        time_base_den=48000,
        duration_num=120,
        duration_den=1,
        duration_basis="duration_ts",
        video_start_num=0,
        video_start_den=1,
        video_start_basis="metadata",
    )


def _agreed_attempt(*, ordinal: int, frame_offset: int, reason: str) -> AudioAlignmentAttempt:
    lag = _frame_lag(frame_offset)
    subframe = _subframe_estimate(lag)
    assert math.floor(subframe + 0.5) == frame_offset
    chunk_count = 4
    candidate = AudioDecisionCandidate(
        frame_offset=frame_offset,
        time_offset_seconds=lag / 8000,
        subframe_estimate=subframe,
        basis="audio_only",
    )
    return AudioAlignmentAttempt(
        reference_identity_digest=_REFERENCE_DIGEST,
        comparison_identity_digest=_COMPARISON_DIGEST,
        comparison_ordinal=ordinal,  # type: ignore[arg-type]
        status="complete",  # type: ignore[arg-type]
        estimator_policy=ALIGNMENT_ESTIMATOR_POLICY,
        diagnostic_policy=_DIAGNOSTIC_POLICY,
        media_runtime_fingerprint="alignment-runtime-test",
        ffmpeg_version="not_observed",
        ffprobe_version="not_observed",
        extraction_recipe="ffmpeg -i <input> -map 0:a -f f32le -",
        fps_num=_FPS_NUM,
        fps_den=_FPS_DEN,
        selected_streams=(
            _stream("reference", _REFERENCE_DIGEST),
            _stream("comparison", _COMPARISON_DIGEST),
        ),
        analysis=AudioAnalysisFacts(
            analysis_rate=8000,
            max_offset_seconds=_MAX_OFFSET_SECONDS,
            chunk_samples=_CHUNK_SAMPLES,
            lag_samples=_LAG_SAMPLES,
            planned_chunk_count=chunk_count,
        ),
        chunks=AudioChunkColumns(
            starts=tuple(index * _CHUNK_SAMPLES for index in range(chunk_count)),
            counts=tuple(_CHUNK_SAMPLES for _ in range(chunk_count)),
            active=(True, True, True, True),
            lags=(lag, lag, lag, lag),
            psrs=(_AGREE_PSR, _AGREE_PSR, _AGREE_PSR, _AGREE_PSR),
            credible=(True, True, True, True),
            agrees=(True, True, True, True),
            total_samples=chunk_count * _CHUNK_SAMPLES,
        ),
        runs=(
            AudioChunkRun(
                first_index=0, last_index=chunk_count - 1, lag=lag, chunk_count=chunk_count
            ),
        ),
        audio=AudioStageOutcome(
            status="agreed",
            global_lag=lag,
            active_chunks=chunk_count,
            credible_chunks=chunk_count,
            agreeing_chunks=chunk_count,
            compensation_seconds=0.0,
            subframe_estimate=subframe,
            rounded_frame=frame_offset,
        ),
        collection_observation="not_observed",
        collection=(),
        video_check=VideoCheckObservation(
            observation="not_observed",
            scored_offsets=(),
            confirmed_offset=None,
            index_build_seconds=None,
            positions=(),
        ),
        decision=AudioAlignmentDecision(
            state="provisional",
            candidate=candidate,
            primary_reason=reason,
            failed_gates=(),
        ),
        stability=AlignmentStabilitySummary(
            classification="stable",
            valid_windows=chunk_count,
            offset_min_frames=frame_offset,
            offset_max_frames=frame_offset,
            first_offset_frames=frame_offset,
            last_offset_frames=frame_offset,
            largest_adjacent_jump_frames=0,
            change_position_seconds=None,
        ),
    )


def provisional_audio_attempt(*, ordinal: int = 1, frame_offset: int = 0) -> AudioAlignmentAttempt:
    """Agreed audio stage awaiting video confirmation (the U3 applied-nothing state)."""
    return _agreed_attempt(ordinal=ordinal, frame_offset=frame_offset, reason="video_check_pending")


def unavailable_audio_attempt(*, ordinal: int = 1) -> AudioAlignmentAttempt:
    """Agreed chunks that still refuse a single offset: no candidate, never applied."""
    empty = AudioChunkColumns(
        starts=(),
        counts=(),
        active=(),
        lags=(),
        psrs=(),
        credible=(),
        agrees=(),
        total_samples=4 * _CHUNK_SAMPLES,
        rows_omitted=True,
    )
    return AudioAlignmentAttempt(
        reference_identity_digest=_REFERENCE_DIGEST,
        comparison_identity_digest=_COMPARISON_DIGEST,
        comparison_ordinal=ordinal,  # type: ignore[arg-type]
        status="complete",  # type: ignore[arg-type]
        estimator_policy=ALIGNMENT_ESTIMATOR_POLICY,
        diagnostic_policy=_DIAGNOSTIC_POLICY,
        media_runtime_fingerprint="alignment-runtime-test",
        ffmpeg_version="not_observed",
        ffprobe_version="not_observed",
        extraction_recipe="ffmpeg -i <input> -map 0:a -f f32le -",
        fps_num=_FPS_NUM,
        fps_den=_FPS_DEN,
        selected_streams=(
            _stream("reference", _REFERENCE_DIGEST),
            _stream("comparison", _COMPARISON_DIGEST),
        ),
        analysis=AudioAnalysisFacts(
            analysis_rate=8000,
            max_offset_seconds=_MAX_OFFSET_SECONDS,
            chunk_samples=_CHUNK_SAMPLES,
            lag_samples=_LAG_SAMPLES,
            planned_chunk_count=4,
        ),
        chunks=empty,
        runs=(),
        audio=AudioStageOutcome(
            status="no_usable_audio",
            global_lag=None,
            active_chunks=0,
            credible_chunks=0,
            agreeing_chunks=0,
            compensation_seconds=0.0,
            subframe_estimate=None,
            rounded_frame=None,
        ),
        collection_observation="not_observed",
        collection=(),
        video_check=VideoCheckObservation(
            observation="not_observed",
            scored_offsets=(),
            confirmed_offset=None,
            index_build_seconds=None,
            positions=(),
        ),
        decision=AudioAlignmentDecision(
            state="unavailable",
            candidate=None,
            primary_reason="no_single_offset",
            failed_gates=("no_single_offset",),
        ),
        stability=AlignmentStabilitySummary(
            classification="insufficient_evidence",
            valid_windows=0,
            offset_min_frames=None,
            offset_max_frames=None,
            first_offset_frames=None,
            last_offset_frames=None,
            largest_adjacent_jump_frames=None,
            change_position_seconds=None,
        ),
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


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
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
    assert output.comparisons[0].audio_attempt == attempt
    assert output.reference.trim.trim_start_frames == 0
    assert output.comparisons[0].trim.trim_start_frames == 0


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
                diagnostic="video_check_pending",
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
    assert output.comparisons[0].audio_attempt == attempt
    assert output.reference.trim.trim_start_frames == 0
    assert output.comparisons[0].trim.trim_start_frames == 0


def test_tampered_diagnostic_cannot_authorize_provisional_alignment_or_trims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode")
    ctx = _context(tmp_path, comparisons=[comparison])
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
        diagnostic="video_check_pending",
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
        )
        assert len(results) == 1
        assert results[0].audio_attempt == attempt
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
    assert output.comparisons[0].audio_attempt == attempt
    assert output.reference.trim.trim_start_frames == 0
    assert output.reference.trim.trim_end_frame_inclusive == 99
    assert output.comparisons[0].trim.trim_start_frames == 0
    assert output.comparisons[0].trim.trim_end_frame_inclusive == 99
