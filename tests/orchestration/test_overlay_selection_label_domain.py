from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.analysis.types import SelectionBreakdown, SelectionDetail
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import (
    ClipFingerprint,
    RunContext,
    SelectionSnapshot,
)
from frame_compare.orchestration.execution import run_render_phase
from frame_compare.orchestration.selection_domain import PreparedSelectionDomain

from .execute_run_helpers import FakeVSLoader, clip_state, install_fake_frame_render
from .phase_task_helpers import _workspace


def test_selection_labels_are_looked_up_in_reference_source_frame_domain_after_trim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = install_fake_frame_render(monkeypatch)

    config = ConfigSchema.model_validate({"screenshots": {"overlay_mode": "standard"}})
    workspace = _workspace(
        tmp_path.resolve(),
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
        config_filename=None,
    )

    fingerprint = ClipFingerprint(Path("ref.mkv"), 1, 1)

    # Reference was trimmed by 10 frames; aligned frame 0 maps to source frame 10.
    reference = clip_state(
        fingerprint.path,
        label="Reference",
        fingerprint=fingerprint,
        width=1920,
        height=1080,
        num_frames=200,
        fps=Fraction(24, 1),
        is_hdr=False,
    ).with_trim(trim_start_frames=10, trim_end_frame_inclusive=None)

    ctx = RunContext(
        config=config,
        workspace=workspace,
        reference=reference,
        comparisons=[],
        reporter=None,
        selection_domain=PreparedSelectionDomain(
            token="test-selection-domain",
            selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=190),
            analysis_clip=None,
        ),
        selection=SelectionSnapshot(breakdown=SelectionBreakdown(quantile_dark=[10])),
    )

    run_render_phase(
        ctx=ctx,
        frames=[0],
        vs_loader=FakeVSLoader(),
    )

    assert [r.overlay.selection_label if r.overlay is not None else None for r in recorded] == [
        "Dark"
    ]


def test_selection_detail_label_is_looked_up_in_reference_source_frame_domain_after_trim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = install_fake_frame_render(monkeypatch)

    config = ConfigSchema.model_validate({"screenshots": {"overlay_mode": "standard"}})
    workspace = _workspace(
        tmp_path.resolve(),
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
        config_filename=None,
    )

    fingerprint = ClipFingerprint(Path("ref.mkv"), 1, 1)
    reference = clip_state(
        fingerprint.path,
        label="Reference",
        fingerprint=fingerprint,
        width=1920,
        height=1080,
        num_frames=200,
        fps=Fraction(24, 1),
        is_hdr=False,
    ).with_trim(trim_start_frames=10, trim_end_frame_inclusive=None)

    ctx = RunContext(
        config=config,
        workspace=workspace,
        reference=reference,
        comparisons=[],
        reporter=None,
        selection_domain=PreparedSelectionDomain(
            token="test-selection-domain",
            selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=190),
            analysis_clip=None,
        ),
        selection=SelectionSnapshot(
            details_by_source_frame={
                10: SelectionDetail(
                    frame_index=10,
                    label="User",
                    source="analysis",
                    timecode="00:00:00.417",
                    clip_role="analyze",
                    notes="user_override",
                )
            }
        ),
    )

    run_render_phase(
        ctx=ctx,
        frames=[0],
        vs_loader=FakeVSLoader(),
    )

    assert [r.overlay.selection_label if r.overlay is not None else None for r in recorded] == [
        "User"
    ]
