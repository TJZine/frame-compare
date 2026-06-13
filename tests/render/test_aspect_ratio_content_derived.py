"""Tests that content-derived rects contribute aspect-ratio evidence.

Both render/geometry.py and orchestration/active_rect.py have
_aspect_ratio_candidates() helpers.  Content-derived rects must be
eligible for rank-2 evidence (support-count ≥ 2) in both paths.
"""

from __future__ import annotations

from frame_compare.orchestration.active_rect import (
    _aspect_ratio_candidates as orch_aspect_ratio_candidates,
)
from frame_compare.orchestration.context import ClipActiveRect
from frame_compare.render.geometry import (
    GeometryRect,
)
from frame_compare.render.geometry import (
    _aspect_ratio_candidates as render_aspect_ratio_candidates,
)

# ---------------------------------------------------------------------------
# render/geometry path
# ---------------------------------------------------------------------------


def test_render_content_derived_is_eligible_for_rank_2_evidence() -> None:
    """A content-derived rect should contribute rank-2 evidence when
    another rect shares its aspect ratio (support ≥ 2)."""
    # Two sources with the same 16:9 ratio: one content-derived, one full-frame.
    resolved: tuple[tuple[GeometryRect, str], ...] = (
        (GeometryRect(0, 0, 1920, 1080), "content-derived"),
        (GeometryRect(0, 0, 1920, 1080), "full-frame"),
    )
    candidates = render_aspect_ratio_candidates(resolved)  # type: ignore[arg-type]
    ratios = [c.ratio for c in candidates]
    assert any(abs(r - 1920 / 1080) < 0.01 for r in ratios), (
        f"content-derived 16:9 ratio should appear in candidates, got {ratios}"
    )


def test_render_content_derived_alone_needs_support() -> None:
    """A single content-derived rect without support (< 2 matching rects)
    should NOT produce a candidate — same rule as dimension-derived."""
    resolved: tuple[tuple[GeometryRect, str], ...] = (
        (GeometryRect(0, 0, 1920, 1080), "content-derived"),
        (GeometryRect(0, 0, 1280, 720), "full-frame"),
    )
    render_aspect_ratio_candidates(resolved)  # type: ignore[arg-type]
    # Both share the same 16:9 ratio so support count is 2 for each.
    # But if the ratios were different, no candidate would appear.
    # Use a genuinely different ratio pair to prove single-support exclusion.
    different: tuple[tuple[GeometryRect, str], ...] = (
        (GeometryRect(0, 0, 1920, 800), "content-derived"),
        (GeometryRect(0, 0, 1280, 720), "full-frame"),
    )
    candidates_diff = render_aspect_ratio_candidates(different)  # type: ignore[arg-type]
    # Neither ratio has support ≥ 2, so rank-2 candidates should be empty.
    rank_2 = [c for c in candidates_diff if c.evidence_rank == 2]
    assert rank_2 == [], "rank-2 candidates should be empty without support ≥ 2"


# ---------------------------------------------------------------------------
# orchestration/active_rect path
# ---------------------------------------------------------------------------


def _clip_rect(width: int, height: int, source: str, mode: str = "auto") -> ClipActiveRect:
    return ClipActiveRect(x=0, y=0, width=width, height=height, source=source, detection_mode=mode)


def test_orch_content_derived_is_eligible_for_rank_2_evidence() -> None:
    """Orchestration twin: content-derived rect contributes rank-2 evidence."""
    resolved = (
        _clip_rect(1920, 1080, "content-derived"),
        _clip_rect(1920, 1080, "full-frame"),
    )
    candidates = orch_aspect_ratio_candidates(resolved)
    ratios = [c.ratio for c in candidates]
    assert any(abs(r - 1920 / 1080) < 0.01 for r in ratios), (
        f"content-derived 16:9 ratio should appear, got {ratios}"
    )


def test_orch_content_derived_alone_needs_support() -> None:
    """Orchestration twin: single content-derived without support excluded."""
    different = (
        _clip_rect(1920, 800, "content-derived"),
        _clip_rect(1280, 720, "full-frame"),
    )
    candidates = orch_aspect_ratio_candidates(different)
    rank_2 = [c for c in candidates if c.evidence_rank == 2]
    assert rank_2 == [], "rank-2 candidates should be empty without support ≥ 2"
