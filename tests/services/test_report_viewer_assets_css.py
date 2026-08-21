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


def test_viewer_css_anchors_toolbar_and_shares_responsive_inspector_width() -> None:
    css = get_css()

    root = css_block(css, ":root")
    assert "--rv-inspector-width: clamp(28rem, 30vw, 42rem);" in root

    toolbar = css_block(css, ".rv-primary-controls")
    assert "display: grid;" in toolbar
    assert "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);" in toolbar
    assert 'grid-template-areas: "frame mode context";' in toolbar

    inspector = css_block(css, ".rv-inspector")
    assert "width: min(var(--rv-inspector-width), calc(100vw - 2rem));" in inspector
    assert "overflow-x: hidden;" in inspector
    stage = css_block(css, "body.rv-inspector-open .rv-viewer-stage")
    assert "margin-right: min(var(--rv-inspector-width), calc(100vw - 2rem));" in stage

    panel = css_block(css, ".rv-inspector-panel")
    assert "overflow-x: hidden;" in panel
    metadata = css_block(css, ".rv-inspector-list")
    assert "grid-template-columns: minmax(5.5rem, max-content) minmax(0, 1fr);" in metadata
