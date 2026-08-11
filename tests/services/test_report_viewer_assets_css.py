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


def test_source_hud_stays_in_viewport_and_wraps_complete_identity() -> None:
    css = get_css()

    stage_labels = css_block(css, ".rv-stage-labels")
    source_label = css_block(css, ".rv-overlay-label")

    assert "position: absolute;" in stage_labels
    assert "inset: 0;" in stage_labels
    assert "max-width: min(48rem, calc(100% - 1.5rem));" in source_label
    assert "top: 52px;" in source_label
    assert "white-space: normal;" in source_label
    assert "text-overflow: ellipsis;" not in source_label
    assert ".rv-mode-diff .rv-stage-labels" not in css

    hidden_hud = css_block(css, ".rv-viewer-stage.rv-overlays-hidden .rv-overlay-label")
    assert "opacity: 0;" in hidden_hud
    assert "visibility: hidden;" in hidden_hud

    mobile = css_block(css, "@media (max-width: 768px)")
    slider_labels = css_block(mobile, ".rv-mode-slider #label-left")
    assert "max-width: calc(50% - 12px);" in slider_labels

    slider_left = css_block(css, ".rv-mode-slider #label-left")
    slider_right = css_block(css, ".rv-mode-slider #label-right")
    assert "left: 12px;" in slider_left
    assert "transform: none;" in slider_left
    assert "right: 12px;" in slider_right
    assert "left: auto;" in slider_right
