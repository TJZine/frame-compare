"""Recovery classification comes from producers, never diagnostic wording."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.analysis.errors import SelectionError, SelectionFailureKind
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.window import (
    ClipWindowInput,
    SelectionWindow,
    compute_shared_selection_window,
)
from frame_compare.config.schema import AnalysisConfig
from frame_compare.config.schema_enums import ScreenshotActiveRectDetection
from frame_compare.orchestration import phase_alignment, phase_selection
from frame_compare.orchestration.full_window_retry import recover_from_exclusion_selection_failure
from tests.orchestration.phase_task_helpers import _clip, _context, _frame_metrics


@pytest.mark.parametrize(
    ("case", "kind", "reason", "requested", "found"),
    [
        ("empty-metrics", SelectionFailureKind.EMPTY_METRICS, "empty_metrics", 1, 0),
        (
            "metric-candidates",
            SelectionFailureKind.INSUFFICIENT_METRIC_CANDIDATES,
            "insufficient_candidates",
            100,
            99,
        ),
        ("no-clips", SelectionFailureKind.NO_CLIPS, "no clips available for selection", 1, 0),
        (
            "empty-window",
            SelectionFailureKind.EMPTY_SELECTION_WINDOW,
            "analysis ignore windows leave no selectable frames",
            1,
            0,
        ),
        (
            "invalid-fps",
            SelectionFailureKind.INVALID_CLIP_FPS,
            "clip fps must be positive for analysis windowing",
            1,
            0,
        ),
        (
            "random",
            SelectionFailureKind.INSUFFICIENT_RANDOM_CANDIDATES,
            "insufficient random candidates after user frames",
            2,
            1,
        ),
        (
            "initial",
            SelectionFailureKind.NO_INITIAL_FRAMES,
            "no selectable user or random frames remain after trims/windowing",
            1,
            0,
        ),
        (
            "reference",
            SelectionFailureKind.EMPTY_REFERENCE_DOMAIN,
            "reference source trims leave no selectable frames",
            0,
            0,
        ),
        (
            "reselect",
            SelectionFailureKind.INSUFFICIENT_ALIGNED_CANDIDATES,
            "insufficient generated candidates after alignment",
            100,
            99,
        ),
        (
            "align-capacity",
            SelectionFailureKind.INSUFFICIENT_ALIGNED_CANDIDATES,
            "insufficient generated candidates after alignment",
            100,
            99,
        ),
        (
            "align-retry",
            SelectionFailureKind.INSUFFICIENT_ALIGNED_CANDIDATES,
            "insufficient generated frames after full-window retry alignment",
            2,
            1,
        ),
    ],
)
def test_real_producers_classify_without_changing_public_payload(
    tmp_path: Path,
    case: str,
    kind: SelectionFailureKind,
    reason: str,
    requested: int,
    found: int,
) -> None:
    ctx = _context(tmp_path)
    metrics = _frame_metrics(
        luminance=[0.1] * 100, motion=[0.0] * 100, frame_count=100, fps=Fraction(24)
    )
    if case in {"metric-candidates", "reselect", "align-capacity"}:
        ctx.reference = _clip(ctx.reference.path, label="Reference", num_frames=99)
        metrics = _frame_metrics(
            luminance=[0.1] * 99, motion=[0.0] * 99, frame_count=99, fps=Fraction(24)
        )
    with pytest.raises(SelectionError) as caught:
        if case in {"empty-metrics", "metric-candidates"}:
            if case == "empty-metrics":
                metrics = _frame_metrics(luminance=[], motion=[], frame_count=0, fps=Fraction(24))
            select_frames(metrics, AnalysisConfig(random_frame_count=0, dark_frame_count=requested))
        elif case in {"no-clips", "empty-window", "invalid-fps"}:
            compute_shared_selection_window(
                []
                if case == "no-clips"
                else [ClipWindowInput(1, Fraction(0) if case == "invalid-fps" else Fraction(24))],
                ignore_lead_seconds=1,
                ignore_trail_seconds=1,
                min_window_seconds=0,
            )
        elif case in {"random", "initial"}:
            ctx.reference = (
                ctx.reference.with_trim(trim_start_frames=10, trim_end_frame_inclusive=19)
                if case == "initial"
                else ctx.reference
            )
            ctx.selection_domain = replace(
                ctx.selection_domain,
                selection_window=SelectionWindow(0, 10 if case == "initial" else 2),
            )
            ctx.config.analysis = AnalysisConfig(
                user_frames=[0], random_frame_count=0 if case == "initial" else 2
            )
            phase_selection.select_initial_frame_plan(ctx)
        elif case == "reference":
            reference = _clip(ctx.reference.path, label="Reference", num_frames=0)
            phase_selection._select_frames_for_selection_domain(
                metrics=metrics,
                reference=reference,
                analysis_clip=reference,
                selection_window=SelectionWindow(0, 0),
                config=ctx.config.analysis,
            )
        elif case == "reselect":
            phase_alignment._reselect_frames_for_trimmed_overlap(
                metrics=metrics,
                reference=ctx.reference,
                comparisons=[],
                selection_source_window=None,
                config=AnalysisConfig(random_frame_count=100),
                accepted_user_source_frames=set(),
            )
        else:
            phase_alignment._normalize_selected_frames_for_trimmed_domain(
                selected_frames=[0],
                user_source_frames=set(),
                reference=ctx.reference,
                comparisons=[],
                selection_source_window=None,
                generated_requested_count=requested,
                seed=7,
                require_full_generated_selection=case == "align-retry",
            )
    assert caught.value.kind is kind
    assert caught.value.context.to_dict() == {
        "code": "FC-4012",
        "name": "SELECTION_ERROR",
        "message": f"Frame selection failed: {reason}",
        "hint": "Adjust selection criteria",
        "details": {"reason": reason, "requested": requested, "found": found},
    }


@pytest.mark.parametrize(
    "classified", [True, False], ids=["reworded-kind", "old-text-unclassified"]
)
def test_recovery_uses_kind_and_keeps_unclassified_errors_fatal(
    tmp_path: Path, classified: bool
) -> None:
    ctx = _context(tmp_path)
    ctx.config.analysis = ctx.config.analysis.model_copy(update={"ignore_lead_seconds": 1.0})
    ctx.config.screenshots.active_rect_detection = ScreenshotActiveRectDetection.ASPECT_RATIO
    authored = ctx.config
    offers = []

    def confirm(request):
        offers.append(request)
        return "confirmed"

    ctx.confirm_full_window_retry = confirm
    error = SelectionError(
        "new diagnostic wording" if classified else "insufficient_candidates",
        requested=3,
        found=1,
        kind=SelectionFailureKind.INSUFFICIENT_METRIC_CANDIDATES
        if classified
        else SelectionFailureKind.UNCLASSIFIED,
    )
    if classified:
        warnings = recover_from_exclusion_selection_failure(ctx, error, vs_loader=None)
        assert len(offers) == 1
        assert len(warnings) == 1
        assert ctx.config.analysis.ignore_lead_seconds == 0
        assert authored.analysis.ignore_lead_seconds == 1
    else:
        with pytest.raises(SelectionError) as caught:
            recover_from_exclusion_selection_failure(ctx, error, vs_loader=None)
        assert caught.value is error
        assert offers == []
