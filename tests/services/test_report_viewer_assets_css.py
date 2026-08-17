from __future__ import annotations

import re

from frame_compare.services.report.viewer import get_css
from tests.services.report_viewer_contracts import css_block


def test_viewer_css_preserves_accessible_input_modes() -> None:
    css = get_css()

    assert "@import" not in css
    assert re.search(r"url\s*\(\s*(['\"]?)\s*https?://", css, re.IGNORECASE) is None
    reduced_motion = css_block(css, "@media (prefers-reduced-motion: reduce)")
    assert "transition: none !important;" in reduced_motion
    assert "animation-duration: 0.01ms !important;" in reduced_motion

    coarse = css_block(css, "@media (pointer: coarse)")
    selectors = (
        "#btn-lens",
        ".rv-lens-palette-controls button",
        ".rv-lens-grip",
        "[data-lens-size]",
        "[data-lens-marker]",
        ".rv-inspector-tabs button",
        ".rv-review-field select",
        ".rv-review-transfer button",
        ".rv-review-preview button",
        ".rv-review-check",
        ".rv-review-preview label",
        "#btn-grid-prev",
        "#btn-grid-next",
        "[data-grid-retry]",
        ".rv-grid-cell",
    )
    for selector in selectors:
        target = css_block(coarse, selector)
        assert "min-width: 44px;" in target, selector
        assert "min-height: 44px;" in target, selector


def test_viewer_css_keeps_hud_on_stage_edges() -> None:
    css = get_css()

    stage = css_block(css, ".rv-viewer-stage")
    assert "flex: 1 1 0;" in stage
    assert "min-height: 0;" in stage
    fullscreen_stage = css_block(css, ".rv-viewer-stage:fullscreen")
    assert "width: 100vw;" in fullscreen_stage
    assert "height: 100vh;" in fullscreen_stage

    source_label = css_block(css, ".rv-overlay-label")
    assert "top: 12px;" in source_label
    assert "left: 12px;" in source_label
    assert ".rv-mode-slider #label-left" not in css
    assert ".rv-mode-slider #label-right" not in css

    palette = css_block(css, "\n.rv-viewport-palette {")
    assert "right: 16px;" in palette
    assert "bottom: 16px;" in palette
