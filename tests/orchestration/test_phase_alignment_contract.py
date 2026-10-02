from __future__ import annotations

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
