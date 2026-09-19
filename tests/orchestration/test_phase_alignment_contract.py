from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from frame_compare.orchestration import phase_alignment
from frame_compare.services import alignment as alignment_service
from frame_compare.services.alignment_consensus import AlignmentConsensus
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import AlignmentClipIdentity, AlignmentClipRequest, AlignmentRequest
from tests.orchestration.phase_task_helpers import _clip, _context, _run_align_phase
from tests.services.test_alignment_diagnostics import audio_attempt


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
    attempt = audio_attempt()

    monkeypatch.setattr(
        phase_alignment,
        "align_clips_from_request",
        lambda *_args, **_kwargs: [
            AlignmentResult(
                reference_clip=ctx.reference.path.name,
                comparison_clip=comparison.path.name,
                frame_offset=None,
                time_offset_seconds=None,
                correlation_score=0.99,
                algorithm="cross_correlation",
                source="computed",
                applied=False,
                diagnostic="insufficient_consensus",
                audio_attempt=attempt,
            )
        ],
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
    attempt = audio_attempt()
    provisional = AlignmentConsensus(
        sample_offset=None,
        score=0.99,
        applied=False,
        diagnostic="insufficient_consensus",
        valid_windows=5,
        consensus_windows=4,
        consensus_ratio=0.8,
        ambiguity_ratio=2.0,
        window_records=attempt.windows,
        decision=attempt.decision,
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
